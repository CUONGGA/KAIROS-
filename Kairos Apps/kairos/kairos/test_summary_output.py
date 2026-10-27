from __future__ import annotations

import json
import unittest

from kairos.summary_output import (
	SUMMARY_OUTPUT_SCHEMA_VERSION,
	SummaryOutputValidationError,
	parse_and_validate_summary_output,
	render_summary_markdown,
)


class TestStructuredSummaryOutput(unittest.TestCase):
	def setUp(self):
		self.evidence_projects = {"E001": "Kairos Apps", "E002": "Gasco-Platform"}
		self.valid_payload = {
			"projects": [
				{
					"project": "Kairos Apps",
					"done": [{"text": "Da dong bo Codex.", "evidence": ["E001"]}],
					"in_progress": [],
					"risks_or_notes": [],
				},
				{
					"project": "Gasco-Platform",
					"done": [],
					"in_progress": [],
					"risks_or_notes": [
						{"text": "Can kiem tra session moi.", "evidence": ["E002"]}
					],
				},
			],
			"omissions": [],
		}

	def test_accepts_grounded_projects_and_renders_in_context_order(self):
		summary = parse_and_validate_summary_output(
			json.dumps(self.valid_payload), self.evidence_projects, ("Gasco-Platform", "Kairos Apps")
		)
		rendered = render_summary_markdown(summary, "2099-12-31", max_chars=4_000)

		self.assertIn("## Báo cáo ngày 2099-12-31", rendered)
		self.assertLess(rendered.index("### Gasco-Platform"), rendered.index("### Kairos Apps"))
		self.assertIn("#### Hoàn thành", rendered)
		self.assertIn("Da dong bo Codex. [E001]", rendered)
		self.assertIn("Can kiem tra session moi. [E002]", rendered)
		self.assertEqual(SUMMARY_OUTPUT_SCHEMA_VERSION, "kairos.summary_output@2")

	def test_rejects_unknown_evidence_ref(self):
		self.valid_payload["projects"][0]["done"][0]["evidence"] = ["E999"]
		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_rejects_cross_project_evidence(self):
		self.valid_payload["projects"][0]["done"][0]["evidence"] = ["E002"]
		with self.assertRaisesRegex(SummaryOutputValidationError, "another project"):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_rejects_unknown_project(self):
		self.valid_payload["projects"][0]["project"] = "Unknown Project"
		with self.assertRaisesRegex(SummaryOutputValidationError, "does not exist"):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_rejects_duplicate_project(self):
		self.valid_payload["projects"][1]["project"] = "Kairos Apps"
		self.valid_payload["projects"][1]["risks_or_notes"] = []
		with self.assertRaisesRegex(SummaryOutputValidationError, "more than once"):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_rejects_missing_context_project(self):
		self.valid_payload["projects"].pop()

		with self.assertRaisesRegex(SummaryOutputValidationError, "missing"):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_rejects_malformed_json_and_claim_without_evidence(self):
		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output("not json", self.evidence_projects)

		self.valid_payload["projects"][0]["done"][0]["evidence"] = []
		with self.assertRaises(SummaryOutputValidationError):
			parse_and_validate_summary_output(json.dumps(self.valid_payload), self.evidence_projects)

	def test_accepts_and_renders_ten_projects_within_default_budget(self):
		evidence_projects = {f"E{number:03d}": f"Project {number:02d}" for number in range(1, 11)}
		payload = {
			"projects": [
				{
					"project": project,
					"done": [{"text": f"Completed work for {project}.", "evidence": [reference]}],
					"in_progress": [],
					"risks_or_notes": [],
				}
				for reference, project in evidence_projects.items()
			],
			"omissions": [],
		}

		summary = parse_and_validate_summary_output(json.dumps(payload), evidence_projects)
		rendered = render_summary_markdown(summary, "2099-12-31", max_chars=4_000)

		self.assertEqual(rendered.count("\n### Project"), 10)
		self.assertIn("Completed work for Project 01. [E001]", rendered)
		self.assertIn("Completed work for Project 10. [E010]", rendered)
		self.assertLessEqual(len(rendered), 4_000)
