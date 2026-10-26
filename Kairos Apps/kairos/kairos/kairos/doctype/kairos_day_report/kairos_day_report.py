# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

ALLOWED_STATUSES = {"draft", "ready", "error"}


class KairosDayReport(Document):
	def validate(self):
		if not self.report_date:
			frappe.throw("report_date cannot be empty.", title="Kairos Day Report")

		self.status = (self.status or "draft").strip().lower()
		if self.status not in ALLOWED_STATUSES:
			frappe.throw(
				f"Invalid status: {self.status}. "
				f"Allowed values: {', '.join(sorted(ALLOWED_STATUSES))}",
				title="Kairos Day Report",
			)

		if (
			not self.is_new()
			and self.has_value_changed("summary_text")
			and not self.flags.get("kairos_generation_save")
		):
			self.generation_mode = "manual"
			self.generation_key = None
			self.generation_error_code = None

