"""Stable keys and non-secret provenance for Day Report generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from kairos.llm_context import CONTEXT_SCHEMA_VERSION, SummaryContext
from kairos.summary_output import SUMMARY_OUTPUT_SCHEMA_VERSION


@dataclass(frozen=True)
class GenerationFingerprint:
	"""Inputs that identify one reproducible LLM generation request."""

	context_hash: str
	context_version: str
	model: str
	prompt_version: str
	prompt_hash: str
	generation_key: str


def build_generation_fingerprint(report_date, context: SummaryContext, settings) -> GenerationFingerprint:
	"""Hash model, prompt and context inputs without including credentials."""
	model = " ".join(str(settings.llm_model or "").split())
	prompt_version = " ".join(str(settings.summary_prompt_version or "").split())
	prompt_payload = _canonical_json(
		{
			"system_prompt": str(settings.day_report_system_prompt or ""),
			"user_prompt_template": str(settings.day_report_user_prompt_template or ""),
			"output_schema_version": SUMMARY_OUTPUT_SCHEMA_VERSION,
			"output_max_chars": getattr(settings, "summary_output_max_chars", None),
		}
	)
	prompt_hash = _sha256(prompt_payload)
	generation_payload = _canonical_json(
		{
			"report_date": str(report_date),
			"context_hash": context.context_hash,
			"context_version": CONTEXT_SCHEMA_VERSION,
			"model": model,
			"prompt_version": prompt_version,
			"prompt_hash": prompt_hash,
		}
	)
	return GenerationFingerprint(
		context_hash=context.context_hash,
		context_version=CONTEXT_SCHEMA_VERSION,
		model=model,
		prompt_version=prompt_version,
		prompt_hash=prompt_hash,
		generation_key=_sha256(generation_payload),
	)


def is_summary_cache_hit(report, fingerprint: GenerationFingerprint, *, force: bool = False) -> bool:
	"""Return true only for a successful LLM result with identical generation inputs."""
	return bool(
		not force
		and report.status == "ready"
		and report.generation_mode == "llm"
		and report.generation_key == fingerprint.generation_key
		and str(report.summary_text or "").strip()
	)


def classify_generation_error(error: Exception) -> str:
	"""Map provider/configuration failures to a safe, bounded code for persistence."""
	message = str(error).lower()
	if (
		"api key" in message
		or "missing key" in message
		or "configuration" in message
		or "requires an llm model" in message
	):
		return "missing_configuration"
	if "http 401" in message or "http 403" in message or "unauthorized" in message:
		return "authentication_error"
	if "http 429" in message or "rate limit" in message or "quota" in message:
		return "rate_limited"
	if "timed out" in message or "timeout" in message:
		return "provider_timeout"
	if "invalid" in message or "empty summary" in message:
		return "invalid_response"
	return "provider_unavailable"


def _canonical_json(value: object) -> str:
	return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: str) -> str:
	return hashlib.sha256(value.encode("utf-8")).hexdigest()
