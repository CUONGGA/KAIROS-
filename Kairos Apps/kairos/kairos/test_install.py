# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.install import KAIROS_COLLECTOR_ROLE, ensure_collector_role


class TestCollectorRole(FrappeTestCase):
	def test_collector_role_exists_without_desk_access(self):
		ensure_collector_role()
		role = frappe.get_doc("Role", KAIROS_COLLECTOR_ROLE)

		self.assertEqual(role.role_name, KAIROS_COLLECTOR_ROLE)
		self.assertFalse(role.desk_access)
