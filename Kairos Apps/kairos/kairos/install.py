# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe

KAIROS_COLLECTOR_ROLE = "Kairos Collector"


def after_install():
	ensure_collector_role()


def after_migrate():
	ensure_collector_role()


def ensure_collector_role():
	"""Create the non-Desk role used by the external event collector."""
	if frappe.db.exists("Role", KAIROS_COLLECTOR_ROLE):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": KAIROS_COLLECTOR_ROLE,
			"desk_access": 0,
		}
	).insert(ignore_permissions=True)
