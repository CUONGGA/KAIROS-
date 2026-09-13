# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
from collections.abc import Mapping

import frappe
from frappe.utils import cint

from kairos.summary import generate_day_report_summary
from kairos.timeline import generate_day_report_timeline

EVENT_FIELDNAMES = {
	"event_id",
	"source",
	"external_id",
	"kind",
	"status",
	"collector_version",
	"occurred_at",
	"activity_date",
	"collected_at",
	"duration_seconds",
	"title",
	"summary",
	"project",
	"tags",
	"raw_payload",
}


@frappe.whitelist()
def upsert_events(events=None):
	"""Create or update Kairos Events idempotently by ``event_id``.

	``events`` may be a list of dictionaries when called in Python or a JSON array
	when sent to Frappe's HTTP method endpoint.
	"""
	if not cint(frappe.db.get_single_value("Kairos Settings", "collection_enabled")):
		frappe.throw("Kairos event collection is disabled in Kairos Settings.")

	payloads = _parse_events(events)
	planned_events = []
	seen_event_ids = set()

	for index, payload in enumerate(payloads, start=1):
		values, event_id = _normalize_event(payload, index)
		if event_id in seen_event_ids:
			frappe.throw(f"Duplicate event_id in request: {event_id}")
		seen_event_ids.add(event_id)

		existing_name = frappe.db.get_value("Kairos Event", {"event_id": event_id}, "name")
		if existing_name:
			document = frappe.get_doc("Kairos Event", existing_name)
			document.update(values)
			action = "updated"
		else:
			document = frappe.get_doc({"doctype": "Kairos Event", **values})
			action = "created"

		# Validate the complete batch before writing any document.
		document.run_method("validate")
		planned_events.append((document, action))

	created = []
	updated = []
	for document, action in planned_events:
		if action == "created":
			document.insert()
			created.append(document.event_id)
		else:
			document.save()
			updated.append(document.event_id)

	return {
		"created": len(created),
		"updated": len(updated),
		"created_event_ids": created,
		"updated_event_ids": updated,
	}


@frappe.whitelist()
def generate_day_timeline(report_date=None):
	"""Create or refresh a Day Report timeline for the selected date."""
	frappe.only_for("System Manager")
	if not report_date:
		frappe.throw("report_date is required.")

	report, timeline = generate_day_report_timeline(report_date)
	return {
		"report_name": report.name,
		"report_date": report.report_date,
		"event_count": timeline.event_count,
		"timeline_text": timeline.text,
	}


@frappe.whitelist()
def generate_day_summary(report_date=None):
	"""Generate an LLM summary for a selected Day Report date."""
	frappe.only_for("System Manager")
	if not report_date:
		frappe.throw("report_date is required.")

	report = generate_day_report_summary(report_date)
	return {
		"report_name": report.name,
		"report_date": report.report_date,
		"status": report.status,
		"summary_text": report.summary_text,
	}


def _parse_events(events) -> list[dict]:
	if isinstance(events, str):
		try:
			events = json.loads(events)
		except json.JSONDecodeError as error:
			frappe.throw(f"events must be a JSON array: {error.msg}")

	if not isinstance(events, list):
		frappe.throw("events must be a JSON array.")
	if not events:
		frappe.throw("events must contain at least one event.")

	return events


def _normalize_event(payload, index: int) -> tuple[dict, str]:
	if not isinstance(payload, Mapping):
		frappe.throw(f"Event at index {index} must be an object.")

	values = {field: value for field, value in payload.items() if field in EVENT_FIELDNAMES}
	source = str(values.get("source") or "").strip().lower()
	external_id = str(values.get("external_id") or "").strip()

	if not source:
		frappe.throw(f"Event at index {index} is missing source.")
	if not external_id:
		frappe.throw(f"Event at index {index} is missing external_id.")
	if not values.get("occurred_at"):
		frappe.throw(f"Event at index {index} is missing occurred_at.")

	event_id = f"{source}:{external_id}"
	provided_event_id = str(values.get("event_id") or "").strip()
	if provided_event_id and provided_event_id != event_id:
		frappe.throw(
			f"Event at index {index} has event_id '{provided_event_id}', expected '{event_id}'."
		)

	values.update({"source": source, "external_id": external_id, "event_id": event_id})
	return values, event_id
