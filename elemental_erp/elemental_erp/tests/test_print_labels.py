"""Static regression checks for employee and packing-label print workflows."""

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
EMPLOYEE_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "employee_id_badge" / "employee_id_badge.json"
PACKING_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "packing_box_label" / "packing_box_label.json"
JOB_SCHEMA = APP_ROOT / "elemental_erp" / "doctype" / "job" / "job.json"
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


if __name__ == "__main__":
	unittest.main()
