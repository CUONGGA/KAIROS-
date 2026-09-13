from __future__ import annotations

import unittest
from pathlib import Path

from kairos_codex.parser import parse_session_file, parse_sessions

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCodexParser(unittest.TestCase):
	def test_parses_session_metadata_and_items(self):
		result = parse_session_file(FIXTURES_DIR / "rollout-valid.jsonl")

		self.assertEqual(len(result.sessions), 1)
		self.assertEqual(result.sessions[0].session_id, "session-test-001")
		self.assertEqual(result.item_count, 3)
		self.assertEqual(result.sessions[0].items[0].record_type, "turn_context")
		self.assertFalse(result.issues)

	def test_keeps_valid_items_after_a_malformed_line(self):
		result = parse_session_file(FIXTURES_DIR / "rollout-malformed.jsonl")

		self.assertEqual(result.sessions[0].session_id, "session-test-002")
		self.assertEqual(result.item_count, 1)
		self.assertEqual(len(result.issues), 1)
		self.assertEqual(result.issues[0].line_number, 2)

	def test_scans_rollout_files_recursively(self):
		result = parse_sessions(FIXTURES_DIR)

		self.assertEqual(len(result.sessions), 3)
		self.assertEqual(result.item_count, 5)
		self.assertEqual(len(result.issues), 1)
