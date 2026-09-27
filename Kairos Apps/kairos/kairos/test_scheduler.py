from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.scheduler import generate_daily_draft


class TestDailyDraftScheduler(FrappeTestCase):
	def setUp(self):
		self.report_date = "2099-12-29"
		self.external_ids = ["scheduler-event-2099", "scheduler-event-update-2099"]
		frappe.db.delete("Kairos Event", {"external_id": ["in", self.external_ids]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})
		self._insert_event(self.external_ids[0], "2099-12-29T02:00:00Z", "Generate scheduled draft")

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"external_id": ["in", self.external_ids]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def test_creates_one_draft_for_the_local_day(self):
		run_at = datetime(2099, 12, 29, 18, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
		report, timeline = generate_daily_draft(run_at)
		repeated_report, repeated_timeline = generate_daily_draft(run_at)

		self.assertEqual(report.name, self.report_date)
		self.assertEqual(report.status, "draft")
		self.assertEqual(timeline.event_count, 1)
		self.assertIn("Generate scheduled draft", report.timeline_text)
		self.assertEqual(repeated_report.name, report.name)
		self.assertEqual(repeated_timeline.event_count, 1)
		self.assertEqual(frappe.db.count("Kairos Day Report", {"report_date": self.report_date}), 1)

	def test_preserves_ready_until_the_timeline_changes(self):
		run_at = datetime(2099, 12, 29, 18, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
		report, _timeline = generate_daily_draft(run_at)
		report.status = "ready"
		report.summary_text = "Existing summary"
		report.save()

		unchanged_report, _timeline = generate_daily_draft(run_at)
		self.assertEqual(unchanged_report.status, "ready")
		self.assertEqual(unchanged_report.summary_text, "Existing summary")

		self._insert_event(self.external_ids[1], "2099-12-29T03:00:00Z", "New scheduled event")
		changed_report, changed_timeline = generate_daily_draft(run_at)
		self.assertEqual(changed_report.status, "draft")
		self.assertEqual(changed_timeline.event_count, 2)

	def _insert_event(self, external_id, occurred_at, title):
		frappe.get_doc(
			{
				"doctype": "Kairos Event",
				"source": "codex",
				"external_id": external_id,
				"event_id": f"codex:{external_id}",
				"occurred_at": occurred_at,
				"title": title,
				"kind": "message",
				"status": "ok",
			}
		).insert(ignore_permissions=True)
