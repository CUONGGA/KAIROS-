from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from kairos_codex.client import FrappeClientConfig, FrappeClientError
from kairos_codex.parser import ParseResult
from kairos_codex.sync import run_sync


class TestSyncIdempotency(unittest.TestCase):
	def setUp(self):
		self.temporary_directory = TemporaryDirectory()
		self.addCleanup(self.temporary_directory.cleanup)
		self.sessions_dir = Path(self.temporary_directory.name) / "sessions"
		self.sessions_dir.mkdir()
		(self.sessions_dir / "rollout-test.jsonl").write_text("{}\n", encoding="utf-8")
		self.state_path = Path(self.temporary_directory.name) / "state.json"
		self.parse_result = ParseResult(sessions=(), issues=())
		self.events = [{"event_id": "codex:session:item"}]
		self.config = FrappeClientConfig("https://kairos.example.test", "key:secret")

	@patch("kairos_codex.sync.parse_sessions")
	@patch("kairos_codex.sync.map_sessions")
	@patch("kairos_codex.sync.load_config")
	@patch("kairos_codex.sync.post_events")
	def test_verifies_second_delivery_only_updates(
		self, post_events, load_config, map_sessions, parse_sessions
	):
		parse_sessions.return_value = self.parse_result
		map_sessions.return_value = self.events
		load_config.return_value = self.config
		post_events.side_effect = [
			{"created": 1, "updated": 0},
			{"created": 0, "updated": 1},
		]

		result = run_sync(
			dry_run=False,
			verify_idempotency=True,
			sessions_dir=self.sessions_dir,
			state_path=self.state_path,
		)

		self.assertEqual(result, 0)
		self.assertEqual(post_events.call_count, 2)

	@patch("kairos_codex.sync.parse_sessions")
	@patch("kairos_codex.sync.map_sessions")
	@patch("kairos_codex.sync.load_config")
	@patch("kairos_codex.sync.post_events")
	def test_fails_when_second_delivery_creates_events(
		self, post_events, load_config, map_sessions, parse_sessions
	):
		parse_sessions.return_value = self.parse_result
		map_sessions.return_value = self.events
		load_config.return_value = self.config
		post_events.side_effect = [
			{"created": 1, "updated": 0},
			{"created": 1, "updated": 0},
		]

		result = run_sync(
			dry_run=False,
			verify_idempotency=True,
			sessions_dir=self.sessions_dir,
			state_path=self.state_path,
		)

		self.assertEqual(result, 2)

	@patch("kairos_codex.sync.parse_sessions")
	@patch("kairos_codex.sync.map_sessions")
	@patch("kairos_codex.sync.load_config")
	@patch("kairos_codex.sync.post_events")
	def test_delivers_events_in_small_batches_and_saves_checkpoint(
		self, post_events, load_config, map_sessions, parse_sessions
	):
		parse_sessions.return_value = self.parse_result
		map_sessions.return_value = [{"event_id": f"codex:session:{index}"} for index in range(201)]
		load_config.return_value = self.config
		post_events.side_effect = [
			{"created": 100, "updated": 0},
			{"created": 100, "updated": 0},
			{"created": 1, "updated": 0},
		]

		result = run_sync(
			dry_run=False,
			sessions_dir=self.sessions_dir,
			state_path=self.state_path,
			batch_size=100,
		)

		self.assertEqual(result, 0)
		self.assertEqual(post_events.call_count, 3)
		self.assertEqual([len(call.args[0]) for call in post_events.call_args_list], [100, 100, 1])
		self.assertTrue(self.state_path.exists())

	@patch("kairos_codex.sync.parse_sessions")
	@patch("kairos_codex.sync.map_sessions")
	@patch("kairos_codex.sync.load_config")
	@patch("kairos_codex.sync.post_events")
	def test_does_not_checkpoint_when_a_batch_fails(self, post_events, load_config, map_sessions, parse_sessions):
		parse_sessions.return_value = self.parse_result
		map_sessions.return_value = [{"event_id": f"codex:session:{index}"} for index in range(101)]
		load_config.return_value = self.config
		post_events.side_effect = [
			{"created": 100, "updated": 0},
			FrappeClientError("request timed out"),
		]

		result = run_sync(
			dry_run=False,
			sessions_dir=self.sessions_dir,
			state_path=self.state_path,
			batch_size=100,
		)

		self.assertEqual(result, 1)
		self.assertFalse(self.state_path.exists())
