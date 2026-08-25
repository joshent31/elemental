"""Static regression checks for employee and packing-label print workflows."""

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
EMPLOYEE_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "employee_id_badge" / "employee_id_badge.json"
PACKING_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "packing_box_label" / "packing_box_label.json"
JOB_TRAVELLER_FORMAT = (
	APP_ROOT
	/ "elemental_erp"
	/ "print_format"
	/ "job_production_traveller"
	/ "job_production_traveller.json"
)
JOB_FG_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "job_fg_qr_label" / "job_fg_qr_label.json"
JOB_SUBPART_FORMAT = (
	APP_ROOT / "elemental_erp" / "print_format" / "job_subpart_qr_label" / "job_subpart_qr_label.json"
)
JOB_ALL_LABELS_FORMAT = (
	APP_ROOT
	/ "elemental_erp"
	/ "print_format"
	/ "job_all_production_qr_labels"
	/ "job_all_production_qr_labels.json"
)
JOB_SCHEMA = APP_ROOT / "elemental_erp" / "doctype" / "job" / "job.json"
JOB_DASHBOARD = APP_ROOT / "elemental_erp" / "doctype" / "job" / "job_dashboard.py"
JOB_CLIENT = APP_ROOT / "public" / "js" / "job.js"
PACKAGING_CLIENT = APP_ROOT / "public" / "js" / "packaging_entry.js"
API_SOURCE = APP_ROOT / "api.py"


class TestEmployeeBadge(unittest.TestCase):
	def test_employee_code_is_printed_below_qr(self):
		html = json.loads(EMPLOYEE_FORMAT.read_text(encoding="utf-8"))["html"]
		qr_position = html.index("doc.employee_qr_image")
		code_position = html.index("Employee Code: {{ doc.name }}")
		self.assertGreater(code_position, qr_position)


class TestPackingBoxLabels(unittest.TestCase):
	def test_job_has_location_and_description_fields(self):
		fields = {
			row["fieldname"]
			for row in json.loads(JOB_SCHEMA.read_text(encoding="utf-8"))["fields"]
		}
		self.assertIn("job_location", fields)
		self.assertIn("job_description", fields)

	def test_label_contains_job_and_sequence_details(self):
		html = json.loads(PACKING_FORMAT.read_text(encoding="utf-8"))["html"]
		for expected in (
			"JOB NO: {{ doc.job }}",
			"job.job_location",
			"job.job_description",
			"LABEL {{ doc.box_no }} OF {{ doc.total_boxes }}",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, html)

	def test_bulk_print_is_available_from_job_and_packaging(self):
		job_client = JOB_CLIENT.read_text(encoding="utf-8")
		packaging_client = PACKAGING_CLIENT.read_text(encoding="utf-8")
		api_source = API_SOURCE.read_text(encoding="utf-8")
		self.assertIn("elemental_print_all_packing_labels", job_client)
		self.assertIn('"Print All Packing Labels"', job_client)
		self.assertIn('"Print All Packing Labels"', packaging_client)
		self.assertIn("def download_packing_labels(job):", api_source)
		self.assertIn("download_multi_pdf", api_source)


class TestJobProductionLabels(unittest.TestCase):
	def test_traveller_prints_job_qr_in_header(self):
		html = json.loads(JOB_TRAVELLER_FORMAT.read_text(encoding="utf-8"))["html"]
		qr_position = html.index("doc.job_qr_image")
		meta_position = html.index('class="meta"')
		self.assertLess(qr_position, meta_position)
		self.assertIn("JOB QR", html)
		self.assertIn("Scan Job QR first", html)

	def test_job_dashboard_exposes_linked_transactions(self):
		dashboard = JOB_DASHBOARD.read_text(encoding="utf-8")
		for expected in (
			'"Job Subpart Label"',
			'"Production Entry"',
			'"Material Indent"',
			'"Packing Box"',
			'"Purchase Order": "elemental_job"',
			'"Sales Invoice": "elemental_job"',
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, dashboard)

	def test_bulk_formats_cover_job_fg_and_subpart_qr(self):
		fg_format = json.loads(JOB_FG_FORMAT.read_text(encoding="utf-8"))
		subpart_format = json.loads(JOB_SUBPART_FORMAT.read_text(encoding="utf-8"))
		all_labels_format = json.loads(JOB_ALL_LABELS_FORMAT.read_text(encoding="utf-8"))

		self.assertEqual(fg_format["doc_type"], "QC Inspection")
		self.assertIn("doc.qr_image", fg_format["html"])
		self.assertEqual(subpart_format["doc_type"], "Job Subpart Label")
		self.assertIn("doc.ref_image", subpart_format["html"])
		self.assertEqual(all_labels_format["doc_type"], "Job")
		for expected in ("doc.job_qr_image", "QC Inspection", "Job Subpart Label"):
			with self.subTest(expected=expected):
				self.assertIn(expected, all_labels_format["html"])

	def test_job_form_exposes_grouped_bulk_print_actions(self):
		job_client = JOB_CLIENT.read_text(encoding="utf-8")
		api_source = API_SOURCE.read_text(encoding="utf-8")
		for expected in (
			'"Bulk Print Labels"',
			'"Print Job + All FG + Subpart Labels"',
			'"Print All FG / QC Labels"',
			'"Print All Subpart Labels"',
			'"Job All Production QR Labels"',
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, job_client)
		for expected in (
			"def download_job_fg_labels(job):",
			"def download_job_subpart_labels(job):",
			'format="Job FG QR Label"',
			'format="Job Subpart QR Label"',
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, api_source)


if __name__ == "__main__":
	unittest.main()
