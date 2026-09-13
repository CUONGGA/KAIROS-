from __future__ import annotations

import unittest
from unittest.mock import patch

from kairos_codex.cli import main


class TestCli(unittest.TestCase):
	def test_sync_dry_run_exits_successfully(self):
		with patch("kairos_codex.cli.run_sync", return_value=0) as run_sync:
			self.assertEqual(main(["sync", "--dry-run"]), 0)

		run_sync.assert_called_once_with(
			dry_run=True,
			verify_idempotency=False,
			sessions_dir=None,
			timeout=30,
			batch_size=100,
			state_path=None,
		)

	def test_verify_idempotency_is_forwarded(self):
		with patch("kairos_codex.cli.run_sync", return_value=0) as run_sync:
			self.assertEqual(main(["sync", "--verify-idempotency"]), 0)

		run_sync.assert_called_once_with(
			dry_run=False,
			verify_idempotency=True,
			sessions_dir=None,
			timeout=30,
			batch_size=100,
			state_path=None,
		)

	def test_no_command_shows_help_and_exits_successfully(self):
		self.assertEqual(main([]), 0)
