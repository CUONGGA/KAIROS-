# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from kairos.secrets import DEFAULT_LLM_BASE_URL, LLM_BASE_URL_ENV_KEY, get_llm_base_url, kairos_secret

CONF_KEY = "kairos_llm_api_key"
ENV_KEY = "KAIROS_LLM_API_KEY"


class TestKairosSecret(FrappeTestCase):
	def setUp(self):
		self.original_conf_value = frappe.conf.get(CONF_KEY)

	def tearDown(self):
		if self.original_conf_value is None:
			frappe.conf.pop(CONF_KEY, None)
		else:
			frappe.conf[CONF_KEY] = self.original_conf_value

	def test_environment_value_takes_precedence(self):
		frappe.conf[CONF_KEY] = "from-site-config"

		with patch.dict(os.environ, {ENV_KEY: "from-environment"}):
			self.assertEqual(kairos_secret(CONF_KEY, ENV_KEY), "from-environment")

	def test_site_config_is_used_when_environment_is_missing(self):
		frappe.conf[CONF_KEY] = "from-site-config"

		with patch.dict(os.environ, {}, clear=False):
			os.environ.pop(ENV_KEY, None)
			self.assertEqual(kairos_secret(CONF_KEY, ENV_KEY), "from-site-config")

	def test_missing_value_raises_a_clear_error(self):
		frappe.conf.pop(CONF_KEY, None)

		with patch.dict(os.environ, {}, clear=False):
			os.environ.pop(ENV_KEY, None)
			with self.assertRaises(frappe.ValidationError) as error:
				kairos_secret(CONF_KEY, ENV_KEY)

		self.assertIn(ENV_KEY, str(error.exception))
		self.assertIn(CONF_KEY, str(error.exception))

	def test_llm_base_url_defaults_to_openai(self):
		frappe.conf.pop("kairos_llm_base_url", None)
		with patch.dict(os.environ, {}, clear=False):
			os.environ.pop(LLM_BASE_URL_ENV_KEY, None)
			self.assertEqual(get_llm_base_url(), DEFAULT_LLM_BASE_URL)
