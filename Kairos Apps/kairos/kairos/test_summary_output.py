from __future__ import annotations

import json
import unittest

from kairos.summary_output import (
	SummaryOutputValidationError,
	parse_and_validate_summary_output,
	render_summary_markdown,
)


class TestStructuredSummaryOutput(unittest.TestCase):
	def setUp(self):
		self.allowed_refs = {"E001", "E002"}
		self.valid_payload = {
			"done": [{"text": "Da dong bo Codex.", "evidence": ["E001"]}],
			"in_progress": [],
			"risks_or_notes": [{"text": "Can kiem tra session moi.", "evidence": ["E002"]}],
			"omissions": [],
		}

	def test_accepts_grounded_claims_and_renders_citations(self):
		summary = parse_and_validate_summary_output(json.dumps(self.valid_payload), self.allowed_refs)

		rendered = render_summary_markdown(summary, "2099-12-31", max_chars=1_200)

		self.assertIn("Da dong bo Codex. [E001]", rendered)
		self.assertIn("Can kiem tra session moi. [E002]", rendered)

	def test_rejects_unknown_evidence_ref(self):
		self.valid_payload["done"][0]["evidence"] = ["E999"]

		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.allowed_refs)

	def test_rejects_malformed_json_and_claim_without_evidence(self):
		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output("not json", self.allowed_refs)

		self.valid_payload["done"][0]["evidence"] = []
		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.allowed_refs)
