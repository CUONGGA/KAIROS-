"""OpenAI-compatible generation for Kairos Day Report summaries."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import frappe

from kairos.secrets import get_llm_api_key, get_llm_base_url
from kairos.timeline import generate_day_report_timeline

LLM_TIMEOUT_SECONDS = 30


def generate_day_report_summary(report_date):
	"""Refresh a day's timeline, then save an LLM-generated summary to its Day Report."""
	report, _timeline = generate_day_report_timeline(report_date)
	settings = frappe.get_single("Kairos Settings")
	messages = _build_messages(settings, report)

	try:
		summary = call_openai_chat_completions(
			base_url=get_llm_base_url(),
			api_key=get_llm_api_key(),
			model=(settings.llm_model or "").strip(),
			messages=messages,
		)
	except Exception:
		report.status = "error"
		report.save(ignore_permissions=True)
		raise

	report.summary_text = summary
	report.status = "ready"
	report.save(ignore_permissions=True)
	return report


def call_openai_chat_completions(*, base_url: str, api_key: str, model: str, messages: list[dict]) -> str:
	"""Send a minimal OpenAI-compatible chat-completions request and return its text."""
	if not model:
		frappe.throw("Kairos Settings requires an LLM Model.", title="Kairos Configuration")

	url = f"{base_url.rstrip('/')}/chat/completions"
	payload = json.dumps({"model": model, "messages": messages}).encode()
	request = Request(
		url,
		data=payload,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		method="POST",
	)

	try:
		with urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
			body = response.read().decode("utf-8")
	except HTTPError as error:
		body = error.read().decode("utf-8", errors="replace")
		frappe.throw(f"LLM returned HTTP {error.code}: {body}", title="Kairos LLM")
	except URLError as error:
		frappe.throw(f"Unable to reach LLM: {error.reason}", title="Kairos LLM")

	try:
		content = json.loads(body)["choices"][0]["message"]["content"]
	except (IndexError, KeyError, TypeError, json.JSONDecodeError):
		frappe.throw("LLM returned an invalid chat-completions response.", title="Kairos LLM")

	if isinstance(content, list):
		content = "".join(
			str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("type") == "text"
		)
	content = str(content).strip()
	if not content:
		frappe.throw("LLM returned an empty summary.", title="Kairos LLM")

	return content


def _build_messages(settings, report) -> list[dict[str, str]]:
	try:
		user_prompt = (settings.day_report_user_prompt_template or "").format(
			date=report.report_date,
			timeline=report.timeline_text or "",
		)
	except KeyError as error:
		frappe.throw(
			f"Unknown placeholder in Day Report User Prompt Template: {error.args[0]}",
			title="Kairos Settings",
		)

	return [
		{"role": "system", "content": (settings.day_report_system_prompt or "").strip()},
		{"role": "user", "content": user_prompt},
	]
