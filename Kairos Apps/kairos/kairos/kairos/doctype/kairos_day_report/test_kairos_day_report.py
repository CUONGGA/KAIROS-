# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class TestKairosDayReport(FrappeTestCase):
	def setUp(self):
		self.report_date = "2099-12-31"
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def tearDown(self):
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def test_create_daily_report_with_default_status(self):
		report = frappe.get_doc(
			{
				"doctype": "Kairos Day Report",
				"report_date": self.report_date,
				"timeline_text": "09:00 - Updated authentication flow",
				"summary_text": "Updated authentication flow.",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(report.name, self.report_date)
		self.assertEqual(report.status, "draft")

	def test_only_one_report_can_exist_per_day(self):
		frappe.get_doc(
			{
				"doctype": "Kairos Day Report",
				"report_date": self.report_date,
			}
		).insert(ignore_permissions=True)

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Kairos Day Report",
					"report_date": self.report_date,
				}
			).insert(ignore_permissions=True)

	def test_rejects_unknown_status(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Kairos Day Report",
					"report_date": self.report_date,
					"status": "published",
				}
			).insert(ignore_permissions=True)
