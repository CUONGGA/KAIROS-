from __future__ import annotations

from unittest import TestCase

from kairos.llm_context import ContextPolicy, build_summary_context_from_events


class TestSummaryContext(TestCase):
	def test_is_deterministic_deduplicated_and_never_includes_raw_payload(self):
		events = [
			{
				"occurred_at": "2099-12-31T03:05:00Z",
				"event_id": "codex:2",
				"source": "codex",
				"kind": "message",
				"title": "Implement context builder",
				"summary": "Added a deterministic JSON envelope and SHA-256 hash.",
				"project": "Kairos",
				"tags": "cli,session:abc",
				"raw_payload": "raw-payload-secret",
			},
			{
				"occurred_at": "2099-12-31T03:00:00Z",
				"event_id": "codex:1",
				"source": "codex",
				"kind": "message",
				"title": "Implement context builder",
				"summary": "",
				"project": "Kairos",
				"tags": "cli",
			},
		]
		policy = ContextPolicy(max_events=10, max_chars=5_000)

		context = build_summary_context_from_events(events, "2099-12-31", policy)
		reversed_context = build_summary_context_from_events(list(reversed(events)), "2099-12-31", policy)

		self.assertEqual(context.to_json(), reversed_context.to_json())
		self.assertEqual(context.context_hash, reversed_context.context_hash)
		self.assertEqual(context.selected_count, 1)
		self.assertEqual(context.deduplicated_count, 1)
		self.assertEqual(context.envelope["events"][0]["ref"], "E001")
		self.assertEqual(context.envelope["events"][0]["occurrence_count"], 2)
		self.assertIn("deterministic JSON envelope", context.to_json())
		self.assertNotIn("raw-payload-secret", context.to_json())

	def test_applies_event_and_character_budgets_without_cutting_json(self):
		events = [
			{
				"occurred_at": f"2099-12-31T0{number}:00:00Z",
				"event_id": f"codex:{number}",
				"source": "codex",
				"kind": "agent_run",
				"title": f"Implement bounded context {number}",
				"summary": "x" * 800,
			}
			for number in range(1, 4)
		]
		context = build_summary_context_from_events(
			events,
			"2099-12-31",
			ContextPolicy(max_events=2, max_chars=1_200),
		)

		self.assertLessEqual(len(context.to_json()), 1_200)
		self.assertLessEqual(context.selected_count, 2)
		self.assertGreater(context.excluded_count, 0)
		self.assertIn("max_chars", context.exclusion_reasons)
		self.assertTrue(
			any("…[truncated]" in event.get("summary", "") for event in context.envelope["events"]),
		)

		max_event_context = build_summary_context_from_events(
			events,
			"2099-12-31",
			ContextPolicy(max_events=1, max_chars=5_000),
		)
		self.assertEqual(max_event_context.selected_count, 1)
		self.assertEqual(max_event_context.exclusion_reasons["max_events"], 2)

	def test_excludes_ineligible_events_and_keeps_stable_references(self):
		events = [
			{
				"occurred_at": "2099-12-31T02:00:00Z",
				"event_id": "codex:ineligible",
				"title": "<environment_context>do not include</environment_context>",
			},
			{
				"occurred_at": "2099-12-31T01:00:00Z",
				"event_id": "codex:first",
				"source": "codex",
				"kind": "message",
				"title": "First activity",
			},
			{
				"occurred_at": "2099-12-31T03:00:00Z",
				"event_id": "codex:second",
				"source": "git",
				"kind": "agent_run",
				"title": "Second activity",
			},
		]
		context = build_summary_context_from_events(events, "2099-12-31")

		self.assertEqual([event["ref"] for event in context.envelope["events"]], ["E001", "E002"])
		self.assertEqual(context.exclusion_reasons["system_or_markup"], 1)
