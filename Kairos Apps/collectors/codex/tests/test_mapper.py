from __future__ import annotations

import json
import unittest
from pathlib import Path

from kairos_codex.mapper import map_session
from kairos_codex.parser import parse_session_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCodexMapper(unittest.TestCase):
	def test_maps_meaningful_items_to_canonical_events(self):
		session = parse_session_file(FIXTURES_DIR / "mapper-session.jsonl").sessions[0]
		events = map_session(session)

		self.assertEqual(len(events), 2)
		self.assertEqual(events[0]["kind"], "message")
		self.assertEqual(events[0]["external_id"], "session-mapper-001:event_msg:line-2")
		self.assertEqual(events[0]["activity_date"], "2026-09-01")
		self.assertEqual(events[0]["project"], "Kairos Apps")
		self.assertEqual(events[0]["tags"], "session:session-mapper-001,cli")
		self.assertEqual(events[1]["kind"], "agent_run")
		self.assertEqual(events[1]["external_id"], "session-mapper-001:turn-001")
		self.assertEqual(events[1]["duration_seconds"], 30)
		self.assertEqual(json.loads(events[1]["raw_payload"])["item_id"], "turn-001")

	def test_maps_task_completion_when_response_message_is_empty(self):
		session = parse_session_file(FIXTURES_DIR / "rollout-valid.jsonl").sessions[0]
		events = map_session(session)

		self.assertEqual(len(events), 1)
		self.assertEqual(events[0]["kind"], "agent_run")

	def test_skips_user_messages_that_are_only_system_markup(self):
		session = parse_session_file(FIXTURES_DIR / "rollout-markup-only.jsonl").sessions[0]

		self.assertEqual(map_session(session), [])
