"""OpenAI-compatible generation for Kairos Day Report summaries."""

from __future__ import annotations

import json
from datetime import timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import frappe
from frappe.utils import get_datetime

from kairos.llm_context import build_day_context
from kairos.quality import sanitize_event_for_llm
from kairos.secrets import get_llm_api_key, get_llm_base_url
from kairos.timeline import KAIROS_TZ, generate_day_report_timeline

LLM_TIMEOUT_SECONDS = 30


def generate_day_report_summary(report_date):
	"""Refresh a timeline and save an LLM summary or a safe local fallback."""
	report, _timeline = generate_day_report_timeline(report_date)
	settings = frappe.get_single("Kairos Settings")
	context = build_day_context(report.report_date)
	safe_timeline = build_llm_safe_timeline(report.report_date)
	messages = _build_messages(settings, report, context.to_json())

	try:
		summary = call_openai_chat_completions(
			base_url=get_llm_base_url(),
			api_key=get_llm_api_key(),
			model=(settings.llm_model or "").strip(),
			messages=messages,
		)
	except frappe.ValidationError:
		frappe.log_error(frappe.get_traceback(), "Kairos Day Report LLM fallback")
		summary = build_fallback_summary(report, safe_timeline)

	report.summary_text = summary
	report.status = "ready"
	report.save(ignore_permissions=True)
	return report


def build_fallback_summary(report, safe_timeline: str | None = None) -> str:
	"""Build a readable report locally without exposing an LLM error to the reader."""
	timeline_text = safe_timeline if safe_timeline is not None else report.timeline_text or ""
	timeline_lines = [line for line in timeline_text.splitlines() if line.strip()]
	if timeline_lines and timeline_lines[0].startswith("Timeline "):
		timeline_lines = timeline_lines[1:]
	timeline_entries = timeline_lines
	entries = "\n".join(f"- {entry}" for entry in timeline_entries)
	if not entries:
		entries = "- Không có hoạt động nào được ghi nhận trong ngày này."

	return (
		f"## Báo cáo ngày {report.report_date}\n\n"
		"### Hoạt động đã ghi nhận\n"
		f"{entries}\n\n"
		"### Ghi chú\n"
		"- Bản tóm tắt dự phòng được tạo từ timeline vì dịch vụ AI hiện không khả dụng."
	)


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
	except TimeoutError:
		frappe.throw("LLM request timed out.", title="Kairos LLM")

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


def build_llm_safe_timeline(report_date) -> str:
	"""Build the LLM-only timeline from sanitized canonical fields, never raw payloads."""
	events = frappe.get_all(
		"Kairos Event",
		filters={"activity_date": report_date},
		fields=["occurred_at", "title", "summary", "project", "source", "event_id"],
		order_by="occurred_at asc, event_id asc",
	)
	lines = []
	for event in events:
		safe_event = sanitize_event_for_llm(event)
		if not safe_event.eligible:
			continue
		lines.append(_format_llm_event(event, safe_event.title, safe_event.project))

	return "\n".join(lines) or "Không có hoạt động đủ điều kiện để gửi tới AI."


def _format_llm_event(event, title: str, project: str) -> str:
	occurred_at = get_datetime(event.occurred_at)
	if occurred_at.tzinfo is None:
		time_label = occurred_at.replace(tzinfo=timezone.utc).astimezone(KAIROS_TZ).strftime("%H:%M")
	else:
		time_label = occurred_at.astimezone(KAIROS_TZ).strftime("%H:%M")
	source = " ".join(str(event.source or "other").split())
	project_suffix = f" ({project})" if project else ""
	return f"{time_label} — [{source}] {title}{project_suffix}"


def _build_messages(settings, report, safe_timeline: str) -> list[dict[str, str]]:
	try:
		user_prompt = (settings.day_report_user_prompt_template or "").format(
			date=report.report_date,
			timeline=safe_timeline,
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
