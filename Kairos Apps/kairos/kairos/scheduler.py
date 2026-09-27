"""Scheduled jobs for Kairos Day Reports."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import frappe

from kairos.timeline import generate_day_report_timeline

KAIROS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def generate_daily_draft(run_at: datetime | None = None):
	"""Create or refresh today's timeline draft without calling an LLM."""
	local_now = run_at.astimezone(KAIROS_TZ) if run_at else datetime.now(KAIROS_TZ)
	report, timeline = generate_day_report_timeline(local_now.date())
	frappe.logger("kairos").info(
		"Daily draft generated: date=%s events=%s status=%s",
		report.report_date,
		timeline.event_count,
		report.status,
	)
	return report, timeline
