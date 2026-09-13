from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kairos_codex.state import changed_paths, load_state, save_state


class TestSyncState(unittest.TestCase):
	def test_tracks_only_new_or_changed_session_files(self):
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			session_path = root / "rollout-session.jsonl"
			state_path = root / "state.json"
			session_path.write_text("first", encoding="utf-8")

			state = load_state(state_path)
			self.assertEqual(changed_paths((session_path,), state), (session_path,))

			save_state(state_path, state, (session_path,))
			self.assertEqual(changed_paths((session_path,), load_state(state_path)), ())

			session_path.write_text("second value", encoding="utf-8")
			self.assertEqual(changed_paths((session_path,), load_state(state_path)), (session_path,))
