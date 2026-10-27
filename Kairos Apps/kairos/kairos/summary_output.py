"""Validated structured output and deterministic rendering for Day Report summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass

SUMMARY_OUTPUT_SCHEMA_VERSION = "kairos.summary_output@1"
DEFAULT_MAX_OUTPUT_CHARS = 1_200
MAX_CLAIM_CHARS = 500
MAX_OMISSION_CHARS = 240
SECTION_NAMES = ("done", "in_progress", "risks_or_notes")
REQUIRED_KEYS = frozenset((*SECTION_NAMES, "omissions"))


class SummaryOutputValidationError(ValueError):
	"""The provider output cannot safely become a Kairos Day Report."""


@dataclass(frozen=True)
class SummaryClaim:
	"""One grounded report statement and the context evidence that supports it."""

	text: str
	evidence: tuple[str, ...]


@dataclass(frozen=True)
class StructuredSummary:
	"""Provider-independent, validated representation of a daily report."""

	done: tuple[SummaryClaim, ...]
	in_progress: tuple[SummaryClaim, ...]
	risks_or_notes: tuple[SummaryClaim, ...]
	omissions: tuple[str, ...]


def parse_and_validate_summary_output(
	raw_output: str,
	allowed_refs: set[str] | frozenset[str] | tuple[str, ...] | list[str],
) -> StructuredSummary:
	"""Parse provider JSON and reject claims without evidence from the supplied context."""
	if not isinstance(raw_output, str) or not raw_output.strip():
		raise SummaryOutputValidationError("output must be a non-empty JSON object")

	try:
		payload = json.loads(raw_output)
	except json.JSONDecodeError as error:
		raise SummaryOutputValidationError("output is not valid JSON") from error

	if not isinstance(payload, dict):
		raise SummaryOutputValidationError("output must be a JSON object")
	if set(payload) != REQUIRED_KEYS:
		raise SummaryOutputValidationError("output has missing or unsupported top-level fields")

	known_refs = {str(reference) for reference in allowed_refs}
	return StructuredSummary(
		done=_parse_claims(payload["done"], "done", known_refs),
		in_progress=_parse_claims(payload["in_progress"], "in_progress", known_refs),
		risks_or_notes=_parse_claims(payload["risks_or_notes"], "risks_or_notes", known_refs),
		omissions=_parse_omissions(payload["omissions"]),
	)


def render_summary_markdown(summary: StructuredSummary, report_date, *, max_chars: int) -> str:
	"""Render validated claims into Kairos-owned Markdown with visible evidence citations."""
	sections = (
		("Ho\u00e0n th\u00e0nh", summary.done),
		("\u0110ang th\u1ef1c hi\u1ec7n", summary.in_progress),
		("R\u1ee7i ro / ghi ch\u00fa", summary.risks_or_notes),
	)
	lines = [f"## Báo cáo ngày {report_date}"]
	for heading, claims in sections:
		if not claims:
			continue
		lines.extend(("", f"### {heading}"))
		lines.extend(f"- {claim.text} [{', '.join(claim.evidence)}]" for claim in claims)

	if summary.omissions:
		lines.extend(("", "### Ph\u1ea1m vi ch\u01b0a bao g\u1ed3m"))
		lines.extend(f"- {item}" for item in summary.omissions)

	if len(lines) == 1:
		lines.extend(("", "- Kh\u00f4ng c\u00f3 ho\u1ea1t \u0111\u1ed9ng \u0111\u1ee7 \u0111i\u1ec1u ki\u1ec7n \u0111\u1ec3 t\u1ed5ng h\u1ee3p."))

	rendered = "\n".join(lines)
	if len(rendered) > max_chars:
		raise SummaryOutputValidationError("rendered summary exceeds the configured output limit")
	return rendered


def _parse_claims(value: object, section: str, allowed_refs: set[str]) -> tuple[SummaryClaim, ...]:
	if not isinstance(value, list):
		raise SummaryOutputValidationError(f"{section} must be an array")

	claims = []
	for item in value:
		if not isinstance(item, dict) or set(item) != {"text", "evidence"}:
			raise SummaryOutputValidationError(f"{section} claims must contain only text and evidence")
		text = _normalized_text(item["text"], MAX_CLAIM_CHARS, f"{section} claim text")
		evidence = _parse_evidence(item["evidence"], allowed_refs, section)
		claims.append(SummaryClaim(text=text, evidence=evidence))
	return tuple(claims)


def _parse_evidence(value: object, allowed_refs: set[str], section: str) -> tuple[str, ...]:
	if not isinstance(value, list) or not value:
		raise SummaryOutputValidationError(f"{section} claims require at least one evidence ref")

	references = []
	for reference in value:
		if not isinstance(reference, str) or reference not in allowed_refs:
			raise SummaryOutputValidationError(f"{section} contains an unknown evidence ref")
		if reference not in references:
			references.append(reference)
	return tuple(references)


def _parse_omissions(value: object) -> tuple[str, ...]:
	if not isinstance(value, list):
		raise SummaryOutputValidationError("omissions must be an array")
	return tuple(_normalized_text(item, MAX_OMISSION_CHARS, "omission") for item in value)


def _normalized_text(value: object, maximum: int, label: str) -> str:
	if not isinstance(value, str):
		raise SummaryOutputValidationError(f"{label} must be text")
	text = " ".join(value.split())
	if not text:
		raise SummaryOutputValidationError(f"{label} must not be empty")
	if len(text) > maximum:
		raise SummaryOutputValidationError(f"{label} exceeds its length limit")
	return text
