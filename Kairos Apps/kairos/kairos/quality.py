"""Safety and quality rules for content that may be sent to an LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass

TITLE_MAX_LENGTH = 160
SUMMARY_MAX_LENGTH = 1000
PROJECT_MAX_LENGTH = 80

_MARKUP_ONLY_PATTERN = re.compile(r"^(?:<[^>]*>\s*)+$")
_SYSTEM_CONTEXT_PREFIXES = ("<environment_context", "&lt;environment_context")
_REDACTED_ONLY_PATTERN = re.compile(
	r"^(?:(?:api[_-]?key|access[_-]?token|auth(?:orization)?|client[_-]?secret|password|secret|token)"
	r"\s*[:=]\s*|Bearer\s+)?\[REDACTED(?: PRIVATE KEY)?\]$",
	re.IGNORECASE,
)
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(
	r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
	re.IGNORECASE | re.DOTALL,
)
_BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
	r"\b(api[_-]?key|access[_-]?token|auth(?:orization)?|client[_-]?secret|password|secret|token)"
	r"(\s*[:=]\s*)([\"']?)([^\s,;\"'}\]]+)(?:\3)",
	re.IGNORECASE,
)
_URL_CREDENTIAL_PATTERN = re.compile(r"\b([a-z][a-z0-9+.-]*://)[^\s/@:]+(?::[^\s/@]+)?@", re.IGNORECASE)
_ABSOLUTE_PATH_PATTERN = re.compile(
	r"(?<![\w:])(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|mnt|private|var|tmp|opt|workspace|workspaces)/)[^\s<>\"']+"
)


@dataclass(frozen=True)
class LLMEvent:
	"""A sanitized event that is safe to include in an LLM context."""

	title: str
	summary: str
	project: str
	eligible: bool
	exclusion_reason: str | None = None


def sanitize_event_for_llm(event: object) -> LLMEvent:
	"""Return bounded, redacted fields and an explicit LLM eligibility decision."""
	title = sanitize_text(_field(event, "title"), max_length=TITLE_MAX_LENGTH)
	summary = sanitize_text(_field(event, "summary"), max_length=SUMMARY_MAX_LENGTH)
	project = sanitize_text(_field(event, "project"), max_length=PROJECT_MAX_LENGTH)

	if not title:
		return LLMEvent(title, summary, project, eligible=False, exclusion_reason="missing_title")
	if _is_system_or_markup(title):
		return LLMEvent(title, summary, project, eligible=False, exclusion_reason="system_or_markup")
	if _REDACTED_ONLY_PATTERN.fullmatch(title):
		return LLMEvent(title, summary, project, eligible=False, exclusion_reason="redacted_only")
	return LLMEvent(title, summary, project, eligible=True)


def sanitize_text(value: object, *, max_length: int) -> str:
	"""Normalize text, redact common credentials, and replace absolute paths."""
	text = " ".join(str(value or "").replace("\x00", " ").split())
	text = _PRIVATE_KEY_BLOCK_PATTERN.sub("[REDACTED PRIVATE KEY]", text)
	text = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", text)
	text = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2[REDACTED]", text)
	text = _URL_CREDENTIAL_PATTERN.sub(r"\1[REDACTED]@", text)
	text = _ABSOLUTE_PATH_PATTERN.sub(_replace_absolute_path, text)
	return text[:max_length].rstrip()


def _field(event: object, fieldname: str) -> object:
	if isinstance(event, dict):
		return event.get(fieldname)
	return getattr(event, fieldname, None)


def _is_system_or_markup(text: str) -> bool:
	lowercase = text.lower()
	return lowercase.startswith(_SYSTEM_CONTEXT_PREFIXES) or bool(_MARKUP_ONLY_PATTERN.fullmatch(text))


def _replace_absolute_path(match: re.Match[str]) -> str:
	parts = [part for part in re.split(r"[\\/]", match.group(0)) if part and part not in {".", ".."}]
	return f"…/{parts[-1]}" if parts else "…/path"
