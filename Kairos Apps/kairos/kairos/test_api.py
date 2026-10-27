# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils import FrappeTestCase

from kairos.api import generate_day_summary, upsert_events


ENDPOINT_SUMMARY_JSON = json.dumps(
	{
		"projects": [
			{
				"project": "Endpoint Project",
				"done": [{"text": "Da kiem tra endpoint.", "evidence": ["E001"]}],
				"in_progress": [],
				"risks_or_notes": [],
			},
			{
				"project": "Second Project",
				"done": [],
				"in_progress": [
					{"text": "Dang kiem tra project thu hai.", "evidence": ["E002"]}
				],
				"risks_or_notes": [],
			}
		],
		"omissions": [],
	}
)


class _EndpointFakeOpenAIHandler(BaseHTTPRequestHandler):
	def do_POST(self):
		if self.path != "/v1/chat/completions":
			self.send_error(404)
			return

		self.server.request_body = self.rfile.read(int(self.headers["Content-Length"]))
		self.server.request_bodies.append(self.server.request_body)
		content = getattr(self.server, "response_content", ENDPOINT_SUMMARY_JSON)
		body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def log_message(self, _format, *_args):
		pass


class TestUpsertEvents(FrappeTestCase):
	def setUp(self):
		self.external_id = "test-api-2099-12-31"
		self.event_id = f"codex:{self.external_id}"
		self.original_collection_enabled = frappe.db.get_single_value(
			"Kairos Settings", "collection_enabled"
		)
		frappe.db.set_single_value("Kairos Settings", "collection_enabled", 1)
		frappe.db.delete("Kairos Event", {"event_id": self.event_id})

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"event_id": self.event_id})
		frappe.db.set_single_value(
			"Kairos Settings", "collection_enabled", self.original_collection_enabled
		)

	def event_payload(self, title="Initial event"):
		return {
			"source": "codex",
			"external_id": self.external_id,
			"occurred_at": "2099-12-31T02:00:00Z",
			"kind": "agent_run",
			"status": "ok",
			"title": title,
		}

	def test_creates_then_updates_the_same_event(self):
		created = upsert_events(events=[self.event_payload()])
		updated = upsert_events(events=[self.event_payload(title="Updated event")])

		self.assertEqual(created["created"], 1)
		self.assertEqual(created["updated"], 0)
		self.assertEqual(updated["created"], 0)
		self.assertEqual(updated["updated"], 1)
		self.assertEqual(frappe.db.count("Kairos Event", {"event_id": self.event_id}), 1)
		self.assertEqual(frappe.db.get_value("Kairos Event", self.event_id, "title"), "Updated event")

	def test_refuses_events_when_collection_is_disabled(self):
		frappe.db.set_single_value("Kairos Settings", "collection_enabled", 0)

		with self.assertRaises(frappe.ValidationError):
			upsert_events(events=[self.event_payload()])

		self.assertFalse(frappe.db.exists("Kairos Event", self.event_id))


class TestDaySummaryAPI(FrappeTestCase):
	@patch("kairos.api.generate_day_report_summary")
	def test_returns_cache_metadata_and_parses_force_flag(self, mock_generate):
		report = SimpleNamespace(
			name="2026-10-10",
			report_date="2026-10-10",
			status="ready",
			summary_text="Done",
			generation_mode="llm",
		)
		mock_generate.return_value = SimpleNamespace(report=report, cache_hit=False)

		response = generate_day_summary("2026-10-10", force="true")

		mock_generate.assert_called_once_with("2026-10-10", force=True)
		self.assertFalse(response["cache_hit"])
		self.assertEqual(response["generation_mode"], "llm")


class TestKairosMethodEndpoints(FrappeAPITestCase):
	"""Exercise Kairos' whitelisted HTTP endpoints through Frappe's test client."""

	report_date = "2098-12-31"
	external_id = "endpoint-e2e-2098"
	second_external_id = "endpoint-e2e-second-2098"
	event_id = f"codex:{external_id}"
	second_event_id = f"codex:{second_external_id}"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.llm_server = ThreadingHTTPServer(("127.0.0.1", 0), _EndpointFakeOpenAIHandler)
		cls.llm_server.request_bodies = []
		cls.llm_thread = threading.Thread(target=cls.llm_server.serve_forever, daemon=True)
		cls.llm_thread.start()

	@classmethod
	def tearDownClass(cls):
		cls.llm_server.shutdown()
		cls.llm_server.server_close()
		cls.llm_thread.join()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		self.llm_server.response_content = ENDPOINT_SUMMARY_JSON
		self.llm_server.request_bodies = []
		self.original_collection_enabled = frappe.db.get_single_value(
			"Kairos Settings", "collection_enabled"
		)
		frappe.db.set_single_value("Kairos Settings", "collection_enabled", 1)
		frappe.db.delete("Kairos Event", {"event_id": ["in", [self.event_id, self.second_event_id]]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"event_id": ["in", [self.event_id, self.second_event_id]]})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})
		frappe.db.set_single_value(
			"Kairos Settings", "collection_enabled", self.original_collection_enabled
		)
		frappe.db.commit()
		super().tearDown()

	def _event_payloads(self):
		return [
			{
				"source": "codex",
				"external_id": self.external_id,
				"occurred_at": "2098-12-31T02:00:00Z",
				"kind": "agent_run",
				"status": "ok",
				"title": "Complete endpoint E2E coverage",
				"summary": "Verified event, timeline, and summary method endpoints.",
				"project": "Endpoint Project",
			},
			{
				"source": "codex",
				"external_id": self.second_external_id,
				"occurred_at": "2098-12-31T03:00:00Z",
				"kind": "message",
				"status": "ok",
				"title": "Verify a second project",
				"summary": "Exercises project-aware evidence validation.",
				"project": "Second Project",
			},
		]

	def _upsert_events(self, events=None):
		return self.post(
			self.method("kairos.api.upsert_events"),
			{
				"sid": self.sid,
				"events": events or self._event_payloads(),
			},
		)

	def test_upsert_events_endpoint_creates_and_updates_multiple_projects(self):
		response = self._upsert_events()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["created"], 2)
		self.assertEqual(
			response.json["message"]["created_event_ids"], [self.event_id, self.second_event_id]
		)
		timeline = self.post(
			self.method("kairos.api.generate_day_timeline"),
			{"sid": self.sid, "report_date": self.report_date},
		)
		self.assertEqual(timeline.status_code, 200)
		self.assertIn("(Endpoint Project)", timeline.json["message"]["timeline_text"])
		self.assertIn("(Second Project)", timeline.json["message"]["timeline_text"])

		updated_payloads = self._event_payloads()
		updated_payloads[0]["title"] = "Updated endpoint E2E coverage"
		updated = self._upsert_events(updated_payloads)
		self.assertEqual(updated.status_code, 200)
		self.assertEqual(updated.json["message"]["updated"], 2)
		updated_timeline = self.post(
			self.method("kairos.api.generate_day_timeline"),
			{"sid": self.sid, "report_date": self.report_date},
		)
		self.assertEqual(updated_timeline.status_code, 200)
		self.assertIn("Updated endpoint E2E coverage", updated_timeline.json["message"]["timeline_text"])

	def test_upsert_events_endpoint_rejects_duplicate_batch_atomically(self):
		duplicate = self._event_payloads()[0]
		response = self._upsert_events([duplicate, dict(duplicate)])

		self.assertNotEqual(response.status_code, 200)
		timeline = self.post(
			self.method("kairos.api.generate_day_timeline"),
			{"sid": self.sid, "report_date": self.report_date},
		)
		self.assertEqual(timeline.status_code, 200)
		self.assertEqual(timeline.json["message"]["event_count"], 0)

	def test_generate_day_timeline_endpoint(self):
		self.assertEqual(self._upsert_events().status_code, 200)

		response = self.post(
			self.method("kairos.api.generate_day_timeline"),
			{"sid": self.sid, "report_date": self.report_date},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["event_count"], 2)
		self.assertIn("Complete endpoint E2E coverage", response.json["message"]["timeline_text"])
		self.assertIn("(Endpoint Project)", response.json["message"]["timeline_text"])
		self.assertIn("(Second Project)", response.json["message"]["timeline_text"])

	def test_generate_day_timeline_endpoint_requires_report_date(self):
		response = self.post(self.method("kairos.api.generate_day_timeline"), {"sid": self.sid})

		self.assertNotEqual(response.status_code, 200)
		self.assertFalse(frappe.db.exists("Kairos Day Report", self.report_date))

	def test_generate_day_summary_endpoint(self):
		self.assertEqual(self._upsert_events().status_code, 200)

		base_url = f"http://127.0.0.1:{self.llm_server.server_port}/v1"
		with patch.dict(
			os.environ,
			{"KAIROS_LLM_API_KEY": "endpoint-e2e-key", "KAIROS_LLM_BASE_URL": base_url},
		):
			response = self.post(
				self.method("kairos.api.generate_day_summary"),
				{"sid": self.sid, "report_date": self.report_date},
			)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["status"], "ready")
		self.assertIn("### Endpoint Project", response.json["message"]["summary_text"])
		self.assertIn("### Second Project", response.json["message"]["summary_text"])
		self.assertIn("Da kiem tra endpoint. [E001]", response.json["message"]["summary_text"])
		self.assertIn("Dang kiem tra project thu hai. [E002]", response.json["message"]["summary_text"])
		self.assertEqual(response.json["message"]["generation_mode"], "llm")
		self.assertFalse(response.json["message"]["cache_hit"])
		request = json.loads(self.llm_server.request_body)
		self.assertIn('"schema_version":"kairos.summary_context@2"', request["messages"][1]["content"])
		self.assertNotIn(self.event_id, request["messages"][1]["content"])

	def test_generate_day_summary_endpoint_reuses_cache_and_force_bypasses_it(self):
		self.assertEqual(self._upsert_events().status_code, 200)
		base_url = f"http://127.0.0.1:{self.llm_server.server_port}/v1"
		with patch.dict(
			os.environ,
			{"KAIROS_LLM_API_KEY": "endpoint-e2e-key", "KAIROS_LLM_BASE_URL": base_url},
		):
			first = self.post(
				self.method("kairos.api.generate_day_summary"),
				{"sid": self.sid, "report_date": self.report_date},
			)
			second = self.post(
				self.method("kairos.api.generate_day_summary"),
				{"sid": self.sid, "report_date": self.report_date},
			)
			forced = self.post(
				self.method("kairos.api.generate_day_summary"),
				{"sid": self.sid, "report_date": self.report_date, "force": "true"},
			)

		self.assertEqual(first.status_code, 200)
		self.assertFalse(first.json["message"]["cache_hit"])
		self.assertTrue(second.json["message"]["cache_hit"])
		self.assertFalse(forced.json["message"]["cache_hit"])
		self.assertEqual(len(self.llm_server.request_bodies), 2)

	def test_generate_day_summary_endpoint_falls_back_for_cross_project_evidence(self):
		self.assertEqual(self._upsert_events().status_code, 200)
		self.llm_server.response_content = json.dumps(
			{
				"projects": [
					{
						"project": "Endpoint Project",
						"done": [{"text": "Cross-project claim.", "evidence": ["E002"]}],
						"in_progress": [],
						"risks_or_notes": [],
					}
				],
				"omissions": [],
			}
		)
		base_url = f"http://127.0.0.1:{self.llm_server.server_port}/v1"
		with patch.dict(
			os.environ,
			{"KAIROS_LLM_API_KEY": "endpoint-e2e-key", "KAIROS_LLM_BASE_URL": base_url},
		):
			response = self.post(
				self.method("kairos.api.generate_day_summary"),
				{"sid": self.sid, "report_date": self.report_date},
			)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["status"], "ready")
		self.assertEqual(response.json["message"]["generation_mode"], "fallback")
		self.assertIn("### Endpoint Project", response.json["message"]["summary_text"])
		self.assertIn("### Second Project", response.json["message"]["summary_text"])
		self.assertEqual(len(self.llm_server.request_bodies), 2)

	def test_generate_day_summary_endpoint_requires_report_date(self):
		response = self.post(self.method("kairos.api.generate_day_summary"), {"sid": self.sid})

		self.assertNotEqual(response.status_code, 200)
