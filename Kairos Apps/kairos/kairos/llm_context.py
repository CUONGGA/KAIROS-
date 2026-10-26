"""Deterministic, budgeted LLM context construction from canonical Kairos Events."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import frappe

from kairos.quality import sanitize_event_for_llm, sanitize_text
from kairos.timeline import KAIROS_TZ

CONTEXT_SCHEMA_VERSION = "kairos.summary_context@1"
DEFAULT_MAX_EVENTS = 150
DEFAULT_MAX_CHARS = 50_000
DEDUPE_WINDOW_SECONDS = 10 * 60
TRUNCATION_MARKER = "…[truncated]"
METADATA_RESERVE_CHARS = 120


@dataclass(frozen=True)
class ContextPolicy:
	"""Non-secret deterministic limits used to select daily summary events."""

	max_events: int = DEFAULT_MAX_EVENTS
	max_chars: int = DEFAULT_MAX_CHARS
	dedupe_window_seconds: int = DEDUPE_WINDOW_SECONDS


@dataclass(frozen=True)
class SummaryContext:
	"""Canonical LLM payload plus auditable selection metadata."""

	envelope: dict[str, Any]
	context_hash: str
	source_event_count: int
	selected_count: int
	excluded_count: int
	deduplicated_count: int
	truncated_count: int
	exclusion_reasons: dict[str, int]

	def to_json(self) -> str:
		return canonical_json(self.envelope)


@dataclass(frozen=True)
class _Candidate:
	occurred_at: datetime
	event_id: str
	source: str
	kind: str
	status: str
	title: str
	summary: str
	project: str
	tags: tuple[str, ...]
	occurrence_count: int = 1


def build_day_context(report_date, policy: ContextPolicy | None = None) -> SummaryContext:
	"""Read one day's canonical events and create a stable, LLM-safe context envelope."""
	settings = frappe.get_single("Kairos Settings")
	resolved_policy = policy or policy_from_settings(settings)
	events = frappe.get_all(
		"Kairos Event",
		filters={"activity_date": report_date},
		fields=["occurred_at", "event_id", "source", "kind", "status", "title", "summary", "project", "tags"],
		order_by="occurred_at asc, event_id asc",
	)
	return build_summary_context_from_events(events, report_date, resolved_policy)


def policy_from_settings(settings) -> ContextPolicy:
	"""Read bounded, non-secret context limits from Kairos Settings."""
	return ContextPolicy(
		max_events=_bounded_int(
			getattr(settings, "summary_context_max_events", None), DEFAULT_MAX_EVENTS, 1, 500
		),
		max_chars=_bounded_int(
			getattr(settings, "summary_context_max_chars", None), DEFAULT_MAX_CHARS, 500, 200_000
		),
	)


def build_summary_context_from_events(
	events: list[object], report_date, policy: ContextPolicy | None = None
) -> SummaryContext:
	"""Build a testable context from event-like values without reading raw payloads."""
	policy = policy or ContextPolicy()
	policy = ContextPolicy(
		max_events=max(1, policy.max_events),
		max_chars=max(500, policy.max_chars),
		dedupe_window_seconds=max(0, policy.dedupe_window_seconds),
	)
	reasons: Counter[str] = Counter()
	candidates = []

	for event in events:
		safe_event = sanitize_event_for_llm(event)
		if not safe_event.eligible:
			reasons[safe_event.exclusion_reason or "ineligible"] += 1
			continue
		occurred_at = _as_utc_datetime(_value(event, "occurred_at"))
		if occurred_at is None:
			reasons["invalid_occurred_at"] += 1
			continue
		candidates.append(
			_Candidate(
				occurred_at=occurred_at,
				event_id=str(_value(event, "event_id") or ""),
				source=sanitize_text(_value(event, "source") or "other", max_length=40) or "other",
				kind=sanitize_text(_value(event, "kind") or "event", max_length=40) or "event",
				status=sanitize_text(_value(event, "status"), max_length=40),
				title=safe_event.title,
				summary=safe_event.summary,
				project=safe_event.project,
				tags=_safe_tags(_value(event, "tags")),
			)
		)

	candidates.sort(key=lambda item: (item.occurred_at, item.event_id))
	deduplicated, duplicate_count = _deduplicate(candidates, policy.dedupe_window_seconds)
	reasons["duplicate"] += duplicate_count

	selected: list[_Candidate] = []
	truncated_count = 0
	for candidate in sorted(deduplicated, key=_selection_key):
		if len(selected) >= policy.max_events:
			reasons["max_events"] += 1
			continue
		fitted, was_truncated = _fit_candidate(
			candidate, selected, report_date, len(events), policy.max_chars, reasons, truncated_count
		)
		if fitted is None:
			reasons["max_chars"] += 1
			continue
		selected.append(fitted)
		truncated_count += int(was_truncated)

	selected.sort(key=lambda item: (item.occurred_at, item.event_id))
	truncated_count = _truncated_count(selected)
	envelope = _build_envelope(selected, report_date, len(events), reasons, truncated_count)
	while selected and len(canonical_json(envelope)) > policy.max_chars:
		selected.pop()
		reasons["max_chars"] += 1
		truncated_count = _truncated_count(selected)
		envelope = _build_envelope(selected, report_date, len(events), reasons, truncated_count)

	payload = canonical_json(envelope)
	return SummaryContext(
		envelope=envelope,
		context_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
		source_event_count=len(events),
		selected_count=len(selected),
		excluded_count=len(events) - len(selected),
		deduplicated_count=duplicate_count,
		truncated_count=truncated_count,
		exclusion_reasons=dict(sorted(reasons.items())),
	)


def canonical_json(value: object) -> str:
	"""Serialize the context with a stable representation before hashing or prompting."""
	return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _deduplicate(candidates: list[_Candidate], window_seconds: int) -> tuple[list[_Candidate], int]:
	kept: list[_Candidate] = []
	last_by_signature: dict[tuple[str, str, str], int] = {}
	duplicates = 0
	for candidate in candidates:
		signature = (candidate.source.lower(), candidate.kind.lower(), " ".join(candidate.title.lower().split()))
		previous_index = last_by_signature.get(signature)
		if previous_index is not None:
			previous = kept[previous_index]
			elapsed = (candidate.occurred_at - previous.occurred_at).total_seconds()
			if elapsed <= window_seconds:
				representative = max((previous, candidate), key=_richness_key)
				kept[previous_index] = replace(representative, occurrence_count=previous.occurrence_count + 1)
				duplicates += 1
				continue
		kept.append(candidate)
		last_by_signature[signature] = len(kept) - 1
	return kept, duplicates


def _fit_candidate(
	candidate: _Candidate,
	selected: list[_Candidate],
	report_date,
	source_count: int,
	max_chars: int,
	reasons: Counter[str],
	truncated_count: int,
) -> tuple[_Candidate | None, bool]:
	if _fits(selected + [candidate], report_date, source_count, max_chars, reasons, truncated_count):
		return candidate, False
	if not candidate.summary:
		return None, False

	low, high = 0, len(candidate.summary)
	best = None
	while low <= high:
		middle = (low + high) // 2
		truncated = _truncate(candidate.summary, middle)
		attempt = replace(candidate, summary=truncated)
		if _fits(selected + [attempt], report_date, source_count, max_chars, reasons, truncated_count + 1):
			best = attempt
			low = middle + 1
		else:
			high = middle - 1
	return (best, best is not None)


def _fits(selected, report_date, source_count, max_chars, reasons, truncated_count) -> bool:
	envelope = _build_envelope(selected, report_date, source_count, reasons, truncated_count)
	return len(canonical_json(envelope)) <= max(1, max_chars - METADATA_RESERVE_CHARS)


def _build_envelope(
	selected, report_date, source_count: int, reasons: Counter[str], truncated_count: int
) -> dict:
	events = []
	for number, candidate in enumerate(selected, start=1):
		event = {
			"ref": f"E{number:03d}",
			"time": candidate.occurred_at.astimezone(KAIROS_TZ).strftime("%H:%M"),
			"source": candidate.source,
			"kind": candidate.kind,
			"title": candidate.title,
		}
		if candidate.summary:
			event["summary"] = candidate.summary
		if candidate.project:
			event["project"] = candidate.project
		if candidate.tags:
			event["tags"] = list(candidate.tags)
		if candidate.occurrence_count > 1:
			event["occurrence_count"] = candidate.occurrence_count
		events.append(event)

	return {
		"schema_version": CONTEXT_SCHEMA_VERSION,
		"report_date": str(report_date),
		"timezone": "Asia/Ho_Chi_Minh",
		"events": events,
		"meta": {
			"source_event_count": source_count,
			"selected_event_count": len(events),
			"excluded_event_count": source_count - len(events),
			"deduplicated_count": reasons.get("duplicate", 0),
			"truncated_count": truncated_count,
			"exclusion_reasons": dict(sorted(reasons.items())),
		},
	}


def _selection_key(candidate: _Candidate) -> tuple[int, datetime, str]:
	priority = 0 if candidate.kind == "agent_run" or candidate.status == "error" else 1
	return priority, candidate.occurred_at, candidate.event_id


def _richness_key(candidate: _Candidate) -> tuple[int, int, str]:
	return bool(candidate.summary), len(candidate.summary), candidate.event_id


def _truncate(value: str, length: int) -> str:
	if length >= len(value):
		return value
	if length <= len(TRUNCATION_MARKER):
		return TRUNCATION_MARKER[:length]
	return f"{value[: length - len(TRUNCATION_MARKER)].rstrip()}{TRUNCATION_MARKER}"


def _truncated_count(candidates: list[_Candidate]) -> int:
	return sum(TRUNCATION_MARKER in candidate.summary for candidate in candidates)


def _safe_tags(value: object) -> tuple[str, ...]:
	values = value.split(",") if isinstance(value, str) else value if isinstance(value, (list, tuple)) else []
	return tuple(filter(None, (sanitize_text(item, max_length=80) for item in values)))[:10]


def _as_utc_datetime(value: object) -> datetime | None:
	if isinstance(value, datetime):
		parsed = value
	elif isinstance(value, str):
		try:
			parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
		except ValueError:
			return None
	else:
		return None
	return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _value(event: object, fieldname: str) -> object:
	return event.get(fieldname) if isinstance(event, dict) else getattr(event, fieldname, None)


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
	try:
		return min(maximum, max(minimum, int(value)))
	except (TypeError, ValueError):
		return default
