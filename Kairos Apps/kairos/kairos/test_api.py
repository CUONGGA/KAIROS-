# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.api import upsert_events


class TestUpsertEvents(FrappeTestCase):
	def setUp(self):
		self.external_id = "test-api-2099-12-31"
		self.event_id = f"codex:{self.external_id}"
		self.original_collection_enabled = frappe.db.get_single_value(
			"Kairos Settings", "collection_enabled"
		)
		frappe.db.set_single_value("Kairos Settings", "collection_enabled", 1)
		frappe.db.delete("Kairos Event", {"event_id": self.event_id})

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"event_id": self.event_id})
		frappe.db.set_single_value(
			"Kairos Settings", "collection_enabled", self.original_collection_enabled
		)

	def event_payload(self, title="Initial event"):
		return {
			"source": "codex",
			"external_id": self.external_id,
			"occurred_at": "2099-12-31T02:00:00Z",
			"kind": "agent_run",
			"status": "ok",
			"title": title,
		}

	def test_creates_then_updates_the_same_event(self):
		created = upsert_events(events=[self.event_payload()])
		updated = upsert_events(events=[self.event_payload(title="Updated event")])

		self.assertEqual(created["created"], 1)
		self.assertEqual(created["updated"], 0)
		self.assertEqual(updated["created"], 0)
		self.assertEqual(updated["updated"], 1)
		self.assertEqual(frappe.db.count("Kairos Event", {"event_id": self.event_id}), 1)
		self.assertEqual(frappe.db.get_value("Kairos Event", self.event_id, "title"), "Updated event")

	def test_refuses_events_when_collection_is_disabled(self):
		frappe.db.set_single_value("Kairos Settings", "collection_enabled", 0)

		with self.assertRaises(frappe.ValidationError):
			upsert_events(events=[self.event_payload()])

		self.assertFalse(frappe.db.exists("Kairos Event", self.event_id))
