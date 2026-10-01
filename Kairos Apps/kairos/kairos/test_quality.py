from __future__ import annotations

from unittest import TestCase

from kairos.quality import sanitize_event_for_llm, sanitize_text


class TestLLMQualityGate(TestCase):
	def test_redacts_secrets_credentials_and_absolute_paths(self):
		text = (
			"Deploy password=super-secret-token to https://kairos:pass@example.test/v1 "
			"from /home/kairos/work/app.py with Bearer abcdefghijklmnop"
		)

		result = sanitize_text(text, max_length=1000)

		self.assertIn("password=[REDACTED]", result)
		self.assertIn("https://[REDACTED]@example.test/v1", result)
		self.assertIn("…/app.py", result)
		self.assertIn("Bearer [REDACTED]", result)
		self.assertNotIn("super-secret-token", result)
		self.assertNotIn("abcdefghijklmnop", result)

	def test_marks_markup_and_redacted_only_events_ineligible(self):
		markup_event = sanitize_event_for_llm({"title": "<environment_context>hidden</environment_context>"})
		redacted_event = sanitize_event_for_llm({"title": "password=super-secret-token"})

		self.assertFalse(markup_event.eligible)
		self.assertEqual(markup_event.exclusion_reason, "system_or_markup")
		self.assertFalse(redacted_event.eligible)
		self.assertEqual(redacted_event.exclusion_reason, "redacted_only")

	def test_bounds_fields_without_inventing_a_summary(self):
		event = sanitize_event_for_llm({"title": "A" * 200, "summary": "B" * 1100, "project": "C" * 100})

		self.assertTrue(event.eligible)
		self.assertEqual(len(event.title), 160)
		self.assertEqual(len(event.summary), 1000)
		self.assertEqual(len(event.project), 80)
