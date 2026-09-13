# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

DEFAULT_SYSTEM_PROMPT = (
	"You are Kairos, a personal AI work assistant. Summarize the user's daily activity "
	"timeline into a clear Vietnamese day report suitable for pasting into Teams. Be concise, "
	"factual, and group related work. Do not invent events that are not in the timeline. "
	"Prefer bullet points and short sections (Done / In progress / Notes) when helpful."
)

DEFAULT_USER_PROMPT_TEMPLATE = (
	"Date: {date}\nTimezone: Asia/Ho_Chi_Minh\n\nActivity timeline:\n{timeline}\n\n"
	"Write a day report in Vietnamese based only on the timeline above."
)


class KairosSettings(Document):
	def validate(self):
		self.timezone = (self.timezone or "").strip() or "Asia/Ho_Chi_Minh"
		if self.timezone != "Asia/Ho_Chi_Minh":
			frappe.throw(
				"MVP chỉ hỗ trợ timezone Asia/Ho_Chi_Minh.",
				title="Kairos Settings",
			)
		if not (self.llm_model or "").strip():
			frappe.throw("llm_model không được trống.", title="Kairos Settings")


def ensure_defaults():
	"""Seed non-secret defaults if Single row is empty. Safe to call more than once."""
	doc = frappe.get_single("Kairos Settings")
	changed = False

	defaults = {
		"llm_model": "gpt-4o-mini",
		"collection_enabled": 1,
		"timezone": "Asia/Ho_Chi_Minh",
		"day_report_system_prompt": DEFAULT_SYSTEM_PROMPT,
		"day_report_user_prompt_template": DEFAULT_USER_PROMPT_TEMPLATE,
	}

	for field, value in defaults.items():
		current = doc.get(field)
		if current in (None, ""):
			doc.set(field, value)
			changed = True

	if changed:
		doc.save()
		frappe.db.commit()

	return {
		"seeded": changed,
		"llm_model": doc.llm_model,
		"collection_enabled": doc.collection_enabled,
		"timezone": doc.timezone,
	}
