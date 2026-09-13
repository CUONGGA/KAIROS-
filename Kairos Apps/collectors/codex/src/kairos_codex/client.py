from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

UPSERT_EVENTS_PATH = "/api/method/kairos.api.upsert_events"
DEFAULT_TIMEOUT_SECONDS = 30


class ClientConfigurationError(ValueError):
	pass


class FrappeClientError(RuntimeError):
	pass


@dataclass(frozen=True)
class FrappeClientConfig:
	base_url: str
	token: str

	@property
	def upsert_events_url(self) -> str:
		return f"{self.base_url.rstrip('/')}{UPSERT_EVENTS_PATH}"


def load_config() -> FrappeClientConfig:
	base_url = (os.environ.get("KAIROS_FRAPPE_URL") or "").strip()
	token = (os.environ.get("KAIROS_FRAPPE_TOKEN") or "").strip()

	if not base_url:
		raise ClientConfigurationError("KAIROS_FRAPPE_URL is required.")
	if not token:
		raise ClientConfigurationError("KAIROS_FRAPPE_TOKEN is required.")

	parsed_url = urlparse(base_url)
	if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
		raise ClientConfigurationError("KAIROS_FRAPPE_URL must be an absolute http(s) URL.")

	return FrappeClientConfig(base_url=base_url, token=token)


def post_events(
	events: list[dict],
	config: FrappeClientConfig,
	*,
	timeout: int = DEFAULT_TIMEOUT_SECONDS,
	opener: Callable[..., Any] | None = None,
) -> dict:
	"""POST canonical events to Frappe and return the API's message object."""
	if not events:
		return {"created": 0, "updated": 0, "created_event_ids": [], "updated_event_ids": []}

	payload = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
	request = Request(
		config.upsert_events_url,
		data=payload,
		method="POST",
		headers={
			"Accept": "application/json",
			"Authorization": f"token {config.token}",
			"Content-Type": "application/json",
			"User-Agent": "kairos-codex/0.1.0",
		},
	)

	try:
		with (opener or urlopen)(request, timeout=timeout) as response:
			body = response.read().decode("utf-8")
	except HTTPError as error:
		details = error.read().decode("utf-8", errors="replace")[:500]
		raise FrappeClientError(f"Frappe returned HTTP {error.code}: {details}") from error
	except (URLError, TimeoutError, OSError) as error:
		reason = getattr(error, "reason", error)
		raise FrappeClientError(f"Could not reach Frappe: {reason}") from error

	try:
		response_data = json.loads(body)
	except json.JSONDecodeError as error:
		raise FrappeClientError("Frappe returned invalid JSON.") from error

	message = response_data.get("message")
	if not isinstance(message, dict):
		raise FrappeClientError("Frappe response did not contain an upsert result.")
	return message
