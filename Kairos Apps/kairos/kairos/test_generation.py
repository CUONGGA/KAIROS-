from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from kairos.generation import build_generation_fingerprint, classify_generation_error, is_summary_cache_hit
from kairos.llm_context import SummaryContext


def _context(context_hash="a" * 64):
	return SummaryContext(
		envelope={},
		context_hash=context_hash,
		source_event_count=1,
		selected_count=1,
		excluded_count=0,
		deduplicated_count=0,
		truncated_count=0,
		exclusion_reasons={},
		evidence_index={},
		project_event_counts={},
		selected_project_counts={},
		project_order=(),
	)


def _settings(**overrides):
	values = {
		"llm_model": "gemini-test",
		"summary_prompt_version": "day-report@1",
		"day_report_system_prompt": "Summarize safely.",
		"day_report_user_prompt_template": "{timeline}",
	}
	values.update(overrides)
	return SimpleNamespace(**values)


class TestGenerationFingerprint(TestCase):
	def test_generation_key_is_stable(self):
		first = build_generation_fingerprint("2026-10-10", _context(), _settings())
		second = build_generation_fingerprint("2026-10-10", _context(), _settings())

		self.assertEqual(first, second)
		self.assertEqual(len(first.generation_key), 64)

	def test_context_model_and_prompt_changes_invalidate_generation_key(self):
		baseline = build_generation_fingerprint("2026-10-10", _context(), _settings())
		changed_context = build_generation_fingerprint("2026-10-10", _context("b" * 64), _settings())
		changed_model = build_generation_fingerprint(
			"2026-10-10", _context(), _settings(llm_model="another-model")
		)
		changed_prompt = build_generation_fingerprint(
			"2026-10-10", _context(), _settings(day_report_system_prompt="A changed prompt")
		)

		self.assertNotEqual(baseline.generation_key, changed_context.generation_key)
		self.assertNotEqual(baseline.generation_key, changed_model.generation_key)
		self.assertNotEqual(baseline.generation_key, changed_prompt.generation_key)

	def test_only_successful_llm_generation_is_cacheable(self):
		fingerprint = build_generation_fingerprint("2026-10-10", _context(), _settings())
		report = SimpleNamespace(
			status="ready",
			generation_mode="llm",
			generation_key=fingerprint.generation_key,
			summary_text="Done",
		)

		self.assertTrue(is_summary_cache_hit(report, fingerprint))
		self.assertFalse(is_summary_cache_hit(report, fingerprint, force=True))
		report.generation_mode = "fallback"
		self.assertFalse(is_summary_cache_hit(report, fingerprint))

	def test_provider_errors_are_reduced_to_safe_codes(self):
		self.assertEqual(
			classify_generation_error(Exception("LLM returned HTTP 429: secret response")), "rate_limited"
		)
		self.assertEqual(classify_generation_error(Exception("Missing API key")), "missing_configuration")
		self.assertEqual(classify_generation_error(Exception("request timed out")), "provider_timeout")
