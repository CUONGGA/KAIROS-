# Copyright (c) 2026, Kairos and contributors
# For license information, please see license.txt

from __future__ import annotations

import os

import frappe

LLM_API_KEY_CONF_KEY = "kairos_llm_api_key"
LLM_API_KEY_ENV_KEY = "KAIROS_LLM_API_KEY"
LLM_BASE_URL_CONF_KEY = "kairos_llm_base_url"
LLM_BASE_URL_ENV_KEY = "KAIROS_LLM_BASE_URL"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"


def kairos_secret(conf_key: str, env_key: str) -> str:
	"""Return a non-empty Kairos secret, preferring an environment variable."""
	value = os.environ.get(env_key) or frappe.conf.get(conf_key)
	value = str(value).strip() if value is not None else ""

	if value:
		return value

	frappe.throw(
		f"Missing Kairos configuration. Set {env_key} or {conf_key} in site_config.",
		title="Kairos Configuration",
	)


def get_llm_api_key() -> str:
	return kairos_secret(LLM_API_KEY_CONF_KEY, LLM_API_KEY_ENV_KEY)


def get_llm_base_url() -> str:
	"""Return an override URL or OpenAI's standard API base URL."""
	value = os.environ.get(LLM_BASE_URL_ENV_KEY) or frappe.conf.get(LLM_BASE_URL_CONF_KEY)
	return str(value).strip().rstrip("/") if value else DEFAULT_LLM_BASE_URL
