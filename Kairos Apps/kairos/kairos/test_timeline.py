from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.timeline import build_timeline, generate_day_report_timeline


class TestTimeline(FrappeTestCase):
	def setUp(self):
		self.report_date = "2099-12-30"
		self.external_ids = ["timeline-earlier-2099", "timeline-later-2099"]
		frappe.db.delete("Kairos Event", {"external_id": ["in", self.external_ids]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"external_id": ["in", self.external_ids]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def test_builds_a_local_time_ordered_timeline(self):
		self._insert_event("timeline-later-2099", "2099-12-30T03:30:00Z", "Later work", "git")
		self._insert_event("timeline-earlier-2099", "2099-12-30T02:00:00Z", "Earlier work", "codex", "Kairos")

		timeline = build_timeline(self.report_date)

		self.assertEqual(timeline.event_count, 2)
		self.assertEqual(
			timeline.text.splitlines(),
			[
				"Timeline 2099-12-30",
				"09:00 — [codex] Earlier work (Kairos)",
				"10:30 — [git] Later work",
			],
		)

	def test_creates_a_draft_report_and_handles_an_empty_day(self):
		report, timeline = generate_day_report_timeline(self.report_date)

		self.assertEqual(report.name, self.report_date)
		self.assertEqual(report.status, "draft")
		self.assertEqual(timeline.event_count, 0)
		self.assertIn("Không có hoạt động", report.timeline_text)

	def _insert_event(self, external_id, occurred_at, title, source, project=None):
		frappe.get_doc(
			{
				"doctype": "Kairos Event",
				"source": source,
				"external_id": external_id,
				"event_id": f"{source}:{external_id}",
				"occurred_at": occurred_at,
				"title": title,
				"project": project,
				"kind": "message",
				"status": "ok",
			}
		).insert(ignore_permissions=True)
