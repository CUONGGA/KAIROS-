from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from kairos_codex.client import ClientConfigurationError, FrappeClientConfig, FrappeClientError, load_config, post_events


class FakeResponse:
	def __init__(self, body: dict):
		self.body = json.dumps(body).encode("utf-8")

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		return False

	def read(self) -> bytes:
		return self.body


class TestFrappeClient(unittest.TestCase):
	def test_environment_configuration(self):
		with patch.dict(
			os.environ,
			{
				"KAIROS_FRAPPE_URL": "https://kairos.example.test/",
				"KAIROS_FRAPPE_TOKEN": "key:secret",
			},
			clear=True,
		):
			config = load_config()

		self.assertEqual(config.upsert_events_url, "https://kairos.example.test/api/method/kairos.api.upsert_events")
		self.assertEqual(config.token, "key:secret")

	def test_missing_configuration_fails_clearly(self):
		with patch.dict(os.environ, {}, clear=True):
			with self.assertRaises(ClientConfigurationError):
				load_config()

	def test_posts_events_with_frappe_token(self):
		captured_request = None

		def opener(request, timeout):
			nonlocal captured_request
			captured_request = request
			self.assertEqual(timeout, 12)
			return FakeResponse({"message": {"created": 1, "updated": 0}})

		result = post_events(
			[{"event_id": "codex:one"}],
			FrappeClientConfig("https://kairos.example.test", "key:secret"),
			timeout=12,
			opener=opener,
		)

		self.assertEqual(result, {"created": 1, "updated": 0})
		self.assertEqual(captured_request.get_method(), "POST")
		self.assertEqual(captured_request.get_header("Authorization"), "token key:secret")
		self.assertEqual(json.loads(captured_request.data), {"events": [{"event_id": "codex:one"}]})

	def test_wraps_network_timeout_as_a_client_error(self):
		def opener(request, timeout):
			raise TimeoutError("timed out")

		with self.assertRaisesRegex(FrappeClientError, "timed out"):
			post_events(
				[{"event_id": "codex:one"}],
				FrappeClientConfig("https://kairos.example.test", "key:secret"),
				opener=opener,
			)
