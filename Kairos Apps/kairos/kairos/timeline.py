from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, getdate

KAIROS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class Timeline:
	report_date: date
	event_count: int
	text: str


def build_timeline(report_date: str | date) -> Timeline:
	"""Build a time-ordered, local-time timeline from Kairos Events for one day."""
	normalized_date = getdate(report_date)
	events = frappe.get_all(
		"Kairos Event",
		filters={"activity_date": normalized_date},
		fields=["occurred_at", "title", "source", "project", "kind", "event_id"],
		order_by="occurred_at asc, event_id asc",
	)
	events = [event for event in events if not _is_system_context_event(event)]

	if not events:
		return Timeline(
			report_date=normalized_date,
			event_count=0,
			text=f"Không có hoạt động nào được ghi nhận ngày {normalized_date.isoformat()}.",
		)

	lines = [f"Timeline {normalized_date.isoformat()}"]
	for event in events:
		lines.append(_format_event(event))
	return Timeline(report_date=normalized_date, event_count=len(events), text="\n".join(lines))


def generate_day_report_timeline(report_date: str | date):
	"""Create or refresh the Day Report timeline without generating an LLM summary."""
	timeline = build_timeline(report_date)
	report_name = timeline.report_date.isoformat()

	if frappe.db.exists("Kairos Day Report", report_name):
		report = frappe.get_doc("Kairos Day Report", report_name)
		report.timeline_text = timeline.text
		report.status = "draft"
		report.save()
	else:
		report = frappe.get_doc(
			{
				"doctype": "Kairos Day Report",
				"report_date": timeline.report_date,
				"status": "draft",
				"timeline_text": timeline.text,
			}
		).insert()

	return report, timeline


def _format_event(event) -> str:
	time_label = _local_time_label(event.occurred_at)
	title = " ".join(str(event.title or "").split())
	if not title:
		title = f"{event.kind or 'event'} {event.event_id}"

	source = str(event.source or "other")
	project = " ".join(str(event.project or "").split())
	project_suffix = f" ({project})" if project else ""
	return f"{time_label} — [{source}] {title}{project_suffix}"


def _local_time_label(value) -> str:
	datetime_value = get_datetime(value)
	if not isinstance(datetime_value, datetime):
		return "--:--"
	if datetime_value.tzinfo is None:
		datetime_value = datetime_value.replace(tzinfo=timezone.utc)
	return datetime_value.astimezone(KAIROS_TZ).strftime("%H:%M")


def _is_system_context_event(event) -> bool:
	title = " ".join(str(event.title or "").split()).lower()
	return title.startswith("<environment_context") or title.startswith("&lt;environment_context")
