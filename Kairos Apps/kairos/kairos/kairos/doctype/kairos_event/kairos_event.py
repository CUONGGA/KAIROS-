# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

KAIROS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TITLE_MAX = 120

ALLOWED_KINDS = {
	"session",
	"message",
	"agent_run",
	"command",
	"commit",
	"file_change",
	"desk_action",
	"note",
	"other",
}

ALLOWED_STATUSES = {"ok", "error", "cancelled", "unknown"}


class KairosEvent(Document):
	def validate(self):
		self.source = (self.source or "").strip().lower()
		self.external_id = (self.external_id or "").strip()
		self.event_id = (self.event_id or "").strip()
		self.title = (self.title or "").strip()
		self.kind = (self.kind or "").strip().lower() or None
		self.status = (self.status or "").strip().lower() or "unknown"
		self.collector_version = (self.collector_version or "").strip() or None
		self.project = (self.project or "").strip() or None
		self.tags = (self.tags or "").strip() or None

		if not self.source:
			frappe.throw("source không được trống.", title="Kairos Event")
		if not self.external_id:
			frappe.throw("external_id không được trống.", title="Kairos Event")

		expected_event_id = f"{self.source}:{self.external_id}"
		if not self.event_id:
			self.event_id = expected_event_id
		elif self.event_id != expected_event_id:
			frappe.throw(
				f"event_id phải là '{expected_event_id}' (source:external_id).",
				title="Kairos Event",
			)

		self.occurred_at = self._normalize_utc_datetime(self.occurred_at, "occurred_at")
		if self.collected_at:
			self.collected_at = self._normalize_utc_datetime(self.collected_at, "collected_at")

		if not self.title:
			if self.summary:
				self.title = " ".join(str(self.summary).split())[:TITLE_MAX]
			else:
				kind_bit = self.kind or "event"
				self.title = f"{kind_bit} {self.external_id}"[:TITLE_MAX]
		elif len(self.title) > TITLE_MAX:
			self.title = self.title[:TITLE_MAX]

		if self.kind and self.kind not in ALLOWED_KINDS:
			frappe.throw(
				f"kind không hợp lệ: {self.kind}. Cho phép: {', '.join(sorted(ALLOWED_KINDS))}",
				title="Kairos Event",
			)

		if self.status not in ALLOWED_STATUSES:
			frappe.throw(
				f"status không hợp lệ: {self.status}. Cho phép: {', '.join(sorted(ALLOWED_STATUSES))}",
				title="Kairos Event",
			)

		self.activity_date = self._derive_activity_date(self.occurred_at)

		if not self.collected_at:
			self.collected_at = now_datetime()

	@staticmethod
	def _derive_activity_date(occurred_at) -> date:
		dt = get_datetime(occurred_at)
		if not isinstance(dt, datetime):
			frappe.throw("occurred_at không hợp lệ.", title="Kairos Event")
		if dt.tzinfo is None:
			# Frappe Datetime is naive UTC by convention for stored values.
			dt = dt.replace(tzinfo=ZoneInfo("UTC"))
		return dt.astimezone(KAIROS_TZ).date()

	@staticmethod
	def _normalize_utc_datetime(value, fieldname: str) -> datetime:
		if not value:
			frappe.throw(f"{fieldname} không được trống.", title="Kairos Event")

		dt = get_datetime(value)
		if not isinstance(dt, datetime):
			frappe.throw(f"{fieldname} không hợp lệ.", title="Kairos Event")
		if dt.tzinfo is None:
			return dt
		return dt.astimezone(timezone.utc).replace(tzinfo=None)
