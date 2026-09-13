from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import PurePath
from zoneinfo import ZoneInfo

from kairos_codex.parser import CodexSession, SessionItem

COLLECTOR_VERSION = "codex@1"
KAIROS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TITLE_MAX = 120
SUMMARY_MAX = 500
MARKUP_ONLY_PATTERN = re.compile(r"^(?:<[^>]*>\s*)+$")
SYSTEM_CONTEXT_PREFIX = "<environment_context"


def map_sessions(sessions: tuple[CodexSession, ...]) -> list[dict]:
	"""Map parsed Codex sessions to canonical Kairos Event dictionaries."""
	events = []
	for session in sessions:
		events.extend(map_session(session))
	return events


def map_session(session: CodexSession) -> list[dict]:
	"""Emit meaningful user requests and completed agent runs from one session."""
	has_event_user_message = any(_is_event_user_message(item) for item in session.items)
	events = []

	for item in session.items:
		kind = _event_kind(item, has_event_user_message=has_event_user_message)
		if not kind:
			continue

		event = _map_item(session, item, kind)
		if event:
			events.append(event)

	return events


def _event_kind(item: SessionItem, *, has_event_user_message: bool) -> str | None:
	payload_type = item.payload.get("type")
	if item.record_type == "event_msg" and payload_type == "user_message":
		return "message" if _has_meaningful_message_text(item) else None
	if item.record_type == "response_item" and payload_type == "message" and item.payload.get("role") == "user":
		return "message" if not has_event_user_message and _has_meaningful_message_text(item) else None
	if item.record_type == "event_msg" and payload_type == "task_complete":
		return "agent_run"
	return None


def _map_item(session: CodexSession, item: SessionItem, kind: str) -> dict | None:
	occurred_at = item.timestamp or session.started_at
	activity_date = _activity_date(occurred_at)
	if not occurred_at or not activity_date:
		return None

	item_id = _item_id(item)
	external_id = f"{session.session_id}:{item_id}"
	text = _item_text(item)
	status = _status(item)
	title = _title(kind, text, status)
	project = _project_name(session.cwd)

	return {
		"source": "codex",
		"external_id": external_id,
		"event_id": f"codex:{external_id}",
		"occurred_at": occurred_at,
		"activity_date": activity_date,
		"title": title,
		"summary": _summary(kind, text, project),
		"kind": kind,
		"status": status,
		"duration_seconds": _duration_seconds(item),
		"project": project,
		"tags": f"session:{session.session_id},{session.originator or 'cli'}",
		"raw_payload": json.dumps(
			{
				"session_id": session.session_id,
				"item_id": item_id,
				"type": item.payload.get("type") or item.record_type,
				"rollout_path": str(PurePath(session.path)),
				"snippet": text[:SUMMARY_MAX],
			},
			ensure_ascii=False,
		),
		"collector_version": COLLECTOR_VERSION,
	}


def _is_event_user_message(item: SessionItem) -> bool:
	return item.record_type == "event_msg" and item.payload.get("type") == "user_message"


def _has_meaningful_message_text(item: SessionItem) -> bool:
	text = _item_text(item)
	return (
		bool(text)
		and not MARKUP_ONLY_PATTERN.fullmatch(text)
		and not text.lower().startswith(SYSTEM_CONTEXT_PREFIX)
	)


def _item_id(item: SessionItem) -> str:
	identifier = item.payload.get("id") or item.payload.get("turn_id")
	if isinstance(identifier, str) and identifier.strip():
		return identifier.strip()
	return f"{item.record_type}:line-{item.line_number}"


def _item_text(item: SessionItem) -> str:
	for field in ("message", "last_agent_message", "text", "summary", "content"):
		text = _extract_text(item.payload.get(field))
		if text:
			return text
	return ""


def _extract_text(value: object) -> str:
	if isinstance(value, str):
		return " ".join(value.split())
	if isinstance(value, list):
		for part in value:
			text = _extract_text(part)
			if text:
				return text
	if isinstance(value, dict):
		for field in ("text", "content", "message", "summary"):
			text = _extract_text(value.get(field))
			if text:
				return text
	return ""


def _status(item: SessionItem) -> str:
	if item.payload.get("type") == "task_complete" and item.payload.get("error"):
		return "error"
	return "ok"


def _title(kind: str, text: str, status: str) -> str:
	if text:
		return text[:TITLE_MAX]
	if kind == "agent_run" and status == "error":
		return "Codex agent run failed"
	if kind == "agent_run":
		return "Codex agent run completed"
	return "Codex user request"


def _summary(kind: str, text: str, project: str | None) -> str:
	prefix = "User request" if kind == "message" else "Agent run"
	project_suffix = f" in {project}" if project else ""
	if text:
		return f"{prefix}{project_suffix}: {text[:SUMMARY_MAX]}"
	return f"{prefix}{project_suffix}."


def _duration_seconds(item: SessionItem) -> float | None:
	duration_ms = item.payload.get("duration_ms")
	if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool):
		return duration_ms / 1000
	return None


def _project_name(cwd: str | None) -> str | None:
	if not cwd:
		return None
	return cwd.rstrip("/\\").replace("\\", "/").rsplit("/", maxsplit=1)[-1] or None


def _activity_date(timestamp: str | None) -> str | None:
	if not timestamp:
		return None
	try:
		datetime_value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
	except ValueError:
		return None
	if datetime_value.tzinfo is None:
		datetime_value = datetime_value.replace(tzinfo=timezone.utc)
	return datetime_value.astimezone(KAIROS_TZ).date().isoformat()
