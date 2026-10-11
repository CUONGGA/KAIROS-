from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.llm_context import build_day_context
from kairos.summary import build_llm_safe_timeline, call_openai_chat_completions, generate_day_report_summary


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
	def do_POST(self):
		if self.path != "/v1/chat/completions":
			self.send_error(404)
			return

		self.server.request_body = self.rfile.read(int(self.headers["Content-Length"]))
		body = json.dumps({"choices": [{"message": {"content": "- E2E summary from local LLM."}}]}).encode()
		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def log_message(self, _format, *_args):
		pass


class TestDayReportSummary(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.llm_server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAIHandler)
		cls.llm_thread = threading.Thread(target=cls.llm_server.serve_forever, daemon=True)
		cls.llm_thread.start()

	@classmethod
	def tearDownClass(cls):
		cls.llm_server.shutdown()
		cls.llm_server.server_close()
		cls.llm_thread.join()
		super().tearDownClass()

	def setUp(self):
		self.report_date = "2099-12-31"
		self.external_id = "summary-event-2099"
		frappe.db.delete("Kairos Event", {"external_id": self.external_id})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})
		frappe.get_doc(
			{
				"doctype": "Kairos Event",
				"source": "codex",
				"external_id": self.external_id,
				"event_id": f"codex:{self.external_id}",
				"occurred_at": "2099-12-31T02:00:00Z",
				"title": "Implement summary generation",
				"kind": "message",
				"status": "ok",
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.delete("Kairos Event", {"external_id": self.external_id})
		frappe.db.delete("Kairos Day Report", {"report_date": self.report_date})

	@patch("kairos.summary.call_openai_chat_completions", return_value="- Completed C2 implementation.")
	def test_generates_and_saves_a_ready_summary(self, mock_completion):
		result = generate_day_report_summary(self.report_date)
		report = result.report

		self.assertFalse(result.cache_hit)
		self.assertEqual(report.status, "ready")
		self.assertEqual(report.summary_text, "- Completed C2 implementation.")
		self.assertEqual(report.generation_mode, "llm")
		self.assertTrue(report.generation_key)
		self.assertTrue(report.context_hash)
		self.assertTrue(report.prompt_hash)
		self.assertEqual(report.context_event_count, 1)
		self.assertIn("Implement summary generation", report.timeline_text)
		self.assertEqual(
			mock_completion.call_args.kwargs["model"],
			frappe.get_single("Kairos Settings").llm_model,
		)
		self.assertIn("Implement summary generation", mock_completion.call_args.kwargs["messages"][1]["content"])
		message = mock_completion.call_args.kwargs["messages"][1]["content"]
		self.assertIn('"schema_version":"kairos.summary_context@1"', message)
		self.assertNotIn("raw_payload", message)

	@patch("kairos.summary.frappe.log_error")
	@patch("kairos.summary.call_openai_chat_completions", side_effect=frappe.ValidationError("LLM failed"))
	def test_generates_a_ready_fallback_when_llm_fails(self, _mock_completion, mock_log_error):
		result = generate_day_report_summary(self.report_date)
		report = result.report

		self.assertFalse(result.cache_hit)
		self.assertEqual(report.status, "ready")
		self.assertIn("Bản tóm tắt dự phòng", report.summary_text)
		self.assertIn("Implement summary generation", report.summary_text)
		self.assertEqual(report.generation_mode, "fallback")
		self.assertFalse(report.generation_key)
		self.assertEqual(report.generation_error_code, "provider_unavailable")
		mock_log_error.assert_called_once()

	@patch("kairos.summary.frappe.log_error")
	@patch("kairos.summary.get_llm_api_key", side_effect=frappe.ValidationError("Missing key"))
	def test_generates_a_fallback_when_llm_key_is_missing(self, _mock_api_key, mock_log_error):
		report = generate_day_report_summary(self.report_date).report

		self.assertEqual(report.status, "ready")
		self.assertIn("dịch vụ AI hiện không khả dụng", report.summary_text)
		self.assertEqual(report.generation_error_code, "missing_configuration")
		mock_log_error.assert_called_once()

	def test_end_to_end_with_a_local_openai_compatible_server(self):
		base_url = f"http://127.0.0.1:{self.llm_server.server_port}/v1"
		with patch.dict(
			os.environ,
			{"KAIROS_LLM_API_KEY": "local-e2e-key", "KAIROS_LLM_BASE_URL": base_url},
		):
			report = generate_day_report_summary(self.report_date).report

		self.assertEqual(report.status, "ready")
		self.assertEqual(report.summary_text, "- E2E summary from local LLM.")
		request = json.loads(self.llm_server.request_body)
		self.assertEqual(request["model"], frappe.get_single("Kairos Settings").llm_model)
		self.assertIn("Implement summary generation", request["messages"][1]["content"])
		self.assertIn('"schema_version":"kairos.summary_context@1"', request["messages"][1]["content"])

	@patch("kairos.summary.call_openai_chat_completions", return_value="Cached summary")
	def test_reuses_successful_summary_for_identical_inputs(self, mock_completion):
		first = generate_day_report_summary(self.report_date)
		second = generate_day_report_summary(self.report_date)

		self.assertFalse(first.cache_hit)
		self.assertTrue(second.cache_hit)
		self.assertEqual(second.report.summary_text, "Cached summary")
		self.assertEqual(mock_completion.call_count, 1)

	@patch("kairos.summary.call_openai_chat_completions", return_value="Forced summary")
	def test_force_regenerate_bypasses_cache(self, mock_completion):
		generate_day_report_summary(self.report_date)
		result = generate_day_report_summary(self.report_date, force=True)

		self.assertFalse(result.cache_hit)
		self.assertEqual(mock_completion.call_count, 2)

	@patch("kairos.summary.call_openai_chat_completions", return_value="Generated summary")
	def test_manual_edit_of_returned_report_invalidates_cache(self, _mock_completion):
		report = generate_day_report_summary(self.report_date).report
		report.summary_text = "Manually edited summary"
		report.save(ignore_permissions=True)

		self.assertEqual(report.generation_mode, "manual")
		self.assertFalse(report.generation_key)

	@patch("kairos.summary.call_openai_chat_completions", return_value="Updated summary")
	def test_event_change_invalidates_cache(self, mock_completion):
		first = generate_day_report_summary(self.report_date)
		event = frappe.get_doc("Kairos Event", f"codex:{self.external_id}")
		event.title = "Implement generation cache"
		event.save(ignore_permissions=True)

		second = generate_day_report_summary(self.report_date)

		self.assertFalse(second.cache_hit)
		self.assertNotEqual(first.report.generation_key, second.report.generation_key)
		self.assertEqual(mock_completion.call_count, 2)

	@patch("kairos.summary.frappe.log_error")
	@patch("kairos.summary.call_openai_chat_completions", side_effect=frappe.ValidationError("LLM failed"))
	def test_fallback_is_not_cached(self, mock_completion, _mock_log_error):
		first = generate_day_report_summary(self.report_date)
		second = generate_day_report_summary(self.report_date)

		self.assertFalse(first.cache_hit)
		self.assertFalse(second.cache_hit)
		self.assertFalse(second.report.generation_key)
		self.assertEqual(mock_completion.call_count, 2)

	@patch("kairos.summary.call_openai_chat_completions", return_value="Stale summary")
	def test_does_not_save_result_when_generation_inputs_change(self, _mock_completion):
		initial_context = build_day_context(self.report_date)
		changed_context = replace(initial_context, context_hash="f" * 64)

		with patch("kairos.summary.build_day_context", side_effect=[initial_context, changed_context]):
			with self.assertRaises(frappe.ValidationError):
				generate_day_report_summary(self.report_date)

		report = frappe.get_doc("Kairos Day Report", self.report_date)
		self.assertEqual(report.status, "draft")
		self.assertNotEqual(report.summary_text, "Stale summary")

	def test_llm_safe_timeline_excludes_raw_payload_and_redacts_event_content(self):
		frappe.get_doc(
			{
				"doctype": "Kairos Event",
				"source": "codex",
				"external_id": "summary-secret-2099",
				"event_id": "codex:summary-secret-2099",
				"occurred_at": "2099-12-31T03:00:00Z",
				"title": "Deploy password=super-secret-token from /home/kairos/private/deploy.py",
				"kind": "message",
				"status": "ok",
				"raw_payload": '{"secret": "raw-payload-secret"}',
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.db.delete, "Kairos Event", {"external_id": "summary-secret-2099"})

		safe_timeline = build_llm_safe_timeline(self.report_date)

		self.assertIn("password=[REDACTED]", safe_timeline)
		self.assertIn("…/deploy.py", safe_timeline)
		self.assertNotIn("super-secret-token", safe_timeline)
		self.assertNotIn("raw-payload-secret", safe_timeline)

	@patch("kairos.summary.urlopen")
	def test_sends_an_openai_compatible_request(self, mock_urlopen):
		response = mock_urlopen.return_value.__enter__.return_value
		response.read.return_value = b'{"choices": [{"message": {"content": "Done"}}]}'

		self.assertEqual(
			call_openai_chat_completions(
				base_url="https://llm.example/v1/",
				api_key="test-key",
				model="test-model",
				messages=[{"role": "user", "content": "Summarize this"}],
			),
			"Done",
		)

		request = mock_urlopen.call_args.args[0]
		self.assertEqual(request.full_url, "https://llm.example/v1/chat/completions")
		self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
		self.assertEqual(
			json.loads(request.data),
			{"model": "test-model", "messages": [{"role": "user", "content": "Summarize this"}]},
		)
