from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.summary import call_openai_chat_completions, generate_day_report_summary


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
		report = generate_day_report_summary(self.report_date)

		self.assertEqual(report.status, "ready")
		self.assertEqual(report.summary_text, "- Completed C2 implementation.")
		self.assertIn("Implement summary generation", report.timeline_text)
		self.assertEqual(
			mock_completion.call_args.kwargs["model"],
			frappe.get_single("Kairos Settings").llm_model,
		)
		self.assertIn("Timeline 2099-12-31", mock_completion.call_args.kwargs["messages"][1]["content"])

	@patch("kairos.summary.call_openai_chat_completions", side_effect=frappe.ValidationError("LLM failed"))
	def test_marks_report_error_when_llm_fails(self, _mock_completion):
		with self.assertRaises(frappe.ValidationError):
			generate_day_report_summary(self.report_date)

		self.assertEqual(frappe.get_doc("Kairos Day Report", self.report_date).status, "error")

	def test_end_to_end_with_a_local_openai_compatible_server(self):
		base_url = f"http://127.0.0.1:{self.llm_server.server_port}/v1"
		with patch.dict(
			os.environ,
			{"KAIROS_LLM_API_KEY": "local-e2e-key", "KAIROS_LLM_BASE_URL": base_url},
		):
			report = generate_day_report_summary(self.report_date)

		self.assertEqual(report.status, "ready")
		self.assertEqual(report.summary_text, "- E2E summary from local LLM.")
		request = json.loads(self.llm_server.request_body)
		self.assertEqual(request["model"], frappe.get_single("Kairos Settings").llm_model)
		self.assertIn("Timeline 2099-12-31", request["messages"][1]["content"])

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
