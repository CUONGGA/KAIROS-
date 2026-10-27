"""Validated structured output and deterministic rendering for Day Report summaries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

SUMMARY_OUTPUT_SCHEMA_VERSION = "kairos.summary_output@2"
DEFAULT_MAX_OUTPUT_CHARS = 4_000
MAX_CLAIM_CHARS = 500
MAX_OMISSION_CHARS = 240
SECTION_NAMES = ("done", "in_progress", "risks_or_notes")
REQUIRED_KEYS = frozenset(("projects", "omissions"))
PROJECT_KEYS = frozenset(("project", *SECTION_NAMES))


class SummaryOutputValidationError(ValueError):
	"""The provider output cannot safely become a Kairos Day Report."""


@dataclass(frozen=True)
class SummaryClaim:
	"""One grounded report statement and the context evidence that supports it."""

	text: str
	evidence: tuple[str, ...]


@dataclass(frozen=True)
class ProjectSummary:
	"""Validated claims for exactly one project from the supplied context."""

	project: str
	done: tuple[SummaryClaim, ...]
	in_progress: tuple[SummaryClaim, ...]
	risks_or_notes: tuple[SummaryClaim, ...]


@dataclass(frozen=True)
class StructuredSummary:
	"""Provider-independent, validated representation of a multi-project daily report."""

	projects: tuple[ProjectSummary, ...]
	omissions: tuple[str, ...]


def parse_and_validate_summary_output(
	raw_output: str,
	evidence_projects: Mapping[str, str],
	project_order: tuple[str, ...] | list[str] | None = None,
) -> StructuredSummary:
	"""Reject malformed claims and evidence that is missing or belongs to another project."""
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

	known_evidence = {str(reference): str(project) for reference, project in evidence_projects.items()}
	ordered_projects = tuple(project_order or sorted(set(known_evidence.values()), key=str.casefold))
	return StructuredSummary(
		projects=_parse_projects(payload["projects"], known_evidence, ordered_projects),
		omissions=_parse_omissions(payload["omissions"]),
	)


def render_summary_markdown(summary: StructuredSummary, report_date, *, max_chars: int) -> str:
	"""Render validated claims into Kairos-owned Markdown with visible evidence citations."""
	lines = [f"## Báo cáo ngày {report_date}"]
	for project_summary in summary.projects:
		sections = (
			("Hoàn thành", project_summary.done),
			("Đang thực hiện", project_summary.in_progress),
			("Rủi ro / ghi chú", project_summary.risks_or_notes),
		)
		lines.extend(("", f"### {project_summary.project}"))
		if not any(claims for _heading, claims in sections):
			lines.append("- Không có claim đủ điều kiện cho project này.")
			continue
		for heading, claims in sections:
			if not claims:
				continue
			lines.extend(("", f"#### {heading}"))
			lines.extend(f"- {claim.text} [{', '.join(claim.evidence)}]" for claim in claims)

	if summary.omissions:
		lines.extend(("", "### Phạm vi chưa bao gồm"))
		lines.extend(f"- {item}" for item in summary.omissions)

	if len(lines) == 1:
		lines.extend(("", "- Không có hoạt động đủ điều kiện để tổng hợp."))

	rendered = "\n".join(lines)
	if len(rendered) > max_chars:
		raise SummaryOutputValidationError("rendered summary exceeds the configured output limit")
	return rendered


def _parse_projects(
	value: object, evidence_projects: dict[str, str], project_order: tuple[str, ...]
) -> tuple[ProjectSummary, ...]:
	if not isinstance(value, list):
		raise SummaryOutputValidationError("projects must be an array")

	allowed_projects = set(evidence_projects.values())
	projects_by_name = {}
	for item in value:
		if not isinstance(item, dict) or set(item) != PROJECT_KEYS:
			raise SummaryOutputValidationError("project summaries contain unsupported or missing fields")
		project = _normalized_text(item["project"], 80, "project")
		if project not in allowed_projects:
			raise SummaryOutputValidationError("project does not exist in the supplied context")
		if project in projects_by_name:
			raise SummaryOutputValidationError("project appears more than once")
		projects_by_name[project] = ProjectSummary(
			project=project,
			done=_parse_claims(item["done"], "done", evidence_projects, project),
			in_progress=_parse_claims(
				item["in_progress"], "in_progress", evidence_projects, project
			),
			risks_or_notes=_parse_claims(
				item["risks_or_notes"], "risks_or_notes", evidence_projects, project
			),
		)
	missing_projects = allowed_projects - set(projects_by_name)
	if missing_projects:
		raise SummaryOutputValidationError("output is missing one or more context projects")

	ordered = [projects_by_name.pop(project) for project in project_order if project in projects_by_name]
	ordered.extend(projects_by_name[project] for project in sorted(projects_by_name, key=str.casefold))
	return tuple(ordered)


def _parse_claims(
	value: object, section: str, evidence_projects: dict[str, str], project: str
) -> tuple[SummaryClaim, ...]:
	if not isinstance(value, list):
		raise SummaryOutputValidationError(f"{section} must be an array")

	claims = []
	for item in value:
		if not isinstance(item, dict) or set(item) != {"text", "evidence"}:
			raise SummaryOutputValidationError(f"{section} claims must contain only text and evidence")
		text = _normalized_text(item["text"], MAX_CLAIM_CHARS, f"{section} claim text")
		evidence = _parse_evidence(item["evidence"], evidence_projects, project, section)
		claims.append(SummaryClaim(text=text, evidence=evidence))
	return tuple(claims)


def _parse_evidence(
	value: object, evidence_projects: dict[str, str], project: str, section: str
) -> tuple[str, ...]:
	if not isinstance(value, list) or not value:
		raise SummaryOutputValidationError(f"{section} claims require at least one evidence ref")

	references = []
	for reference in value:
		if not isinstance(reference, str) or reference not in evidence_projects:
			raise SummaryOutputValidationError(f"{section} contains an unknown evidence ref")
		if evidence_projects[reference] != project:
			raise SummaryOutputValidationError(f"{section} contains evidence from another project")
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
