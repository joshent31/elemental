"""Static regression checks for employee and packing-label print workflows."""

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
EMPLOYEE_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "employee_id_badge" / "employee_id_badge.json"
PACKING_FORMAT = APP_ROOT / "elemental_erp" / "print_format" / "packing_box_label" / "packing_box_label.json"
PACKING_BULK_TEMPLATE = APP_ROOT / "templates" / "print_formats" / "packing_box_labels.html"
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
LABEL_PRINT_PAGE = (
	APP_ROOT / "elemental_erp" / "page" / "label_print_center" / "label_print_center.js"
)
LABEL_PRINT_PAGE_SCHEMA = (
	APP_ROOT / "elemental_erp" / "page" / "label_print_center" / "label_print_center.json"
)
WORKSPACE = (
	APP_ROOT / "elemental_erp" / "workspace" / "elemental_fixtures" / "elemental_fixtures.json"
)
HOOKS_SOURCE = APP_ROOT / "hooks.py"
API_SOURCE = APP_ROOT / "api.py"


class TestEmployeeBadge(unittest.TestCase):
	def test_employee_code_is_printed_below_qr(self):
		html = json.loads(EMPLOYEE_FORMAT.read_text(encoding="utf-8"))["html"]
		qr_position = html.index("doc.employee_qr_image")
		code_position = html.index("Employee Code: {{ doc.name }}")
		self.assertGreater(code_position, qr_position)


class TestPackingBoxLabels(unittest.TestCase):
	def test_job_has_location_without_duplicate_description_field(self):
		job_schema = json.loads(JOB_SCHEMA.read_text(encoding="utf-8"))
		fields = {row["fieldname"] for row in job_schema["fields"]}
		self.assertIn("job_location", fields)
		self.assertNotIn("job_description", fields)

	def test_operational_label_roles_can_print_jobs(self):
		job_schema = json.loads(JOB_SCHEMA.read_text(encoding="utf-8"))
		permissions = {row["role"]: row for row in job_schema["permissions"]}
		for role in (
			"Elemental Data Entry User",
			"Elemental Production User",
			"Elemental QC User",
			"Elemental Packaging User",
		):
			with self.subTest(role=role):
				self.assertEqual(permissions[role].get("print"), 1)

	def test_label_contains_job_and_sequence_details(self):
		html = json.loads(PACKING_FORMAT.read_text(encoding="utf-8"))["html"]
		for expected in (
			"JOB NO: {{ doc.job }}",
			"job.job_location",
			"job.job_name",
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
		self.assertIn("def download_packing_labels(job, box_from=None, box_to=None):", api_source)
		self.assertIn("download_multi_pdf", api_source)

	def test_job_script_is_registered_on_the_job_doctype(self):
		hooks = HOOKS_SOURCE.read_text(encoding="utf-8")
		self.assertIn('"Job": "public/js/job.js"', hooks)
		self.assertNotIn('app_include_js = "/assets/elemental_erp/js/job.js"', hooks)

	def test_print_center_supports_packing_box_ranges(self):
		page = LABEL_PRINT_PAGE.read_text(encoding="utf-8")
		api_source = API_SOURCE.read_text(encoding="utf-8")
		for expected in (
			"From Box No.",
			"To Box No.",
			"Generate &amp; Print All",
			"Create &amp; Print New Range",
			"New From Box No.",
			"New To Box No.",
			"Print Selected Range",
			"Print All Packing Labels",
			"create_packing_labels",
			"create_packing_label_range",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, page)
		for expected in (
			'filters = [["job", "=", job], ["status", "!=", "Cancelled"]]',
			'filters.extend([["box_no", ">=", box_from], ["box_no", "<=", box_to]])',
			"missing_numbers",
			"def get_label_print_center_data(job):",
			"def create_packing_label_range(job, box_from, box_to):",
			"expected_from = last_existing + 1",
			'frappe.db.set_value("Job", job, "total_packing_boxes", box_to)',
			'"Packing Box", existing_box.name, "total_boxes", box_to',
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, api_source)

	def test_bulk_packing_pdf_is_rendered_in_one_pass(self):
		api_source = API_SOURCE.read_text(encoding="utf-8")
		packing_method = api_source.split("def download_packing_labels", 1)[1].split(
			"def _require_production_label_roles", 1
		)[0]
		template = PACKING_BULK_TEMPLATE.read_text(encoding="utf-8")
		self.assertIn("from frappe.utils.pdf import get_pdf", packing_method)
		self.assertNotIn("download_multi_pdf", packing_method)
		self.assertNotIn("frappe.utils.get_url", packing_method)
		self.assertIn("frappe.local.response.filecontent = pdf", packing_method)
		self.assertIn("{% for box in boxes %}", template)
		self.assertIn("data:image/png;base64", packing_method)

	def test_print_center_is_installed_and_linked_in_workspace(self):
		page = json.loads(LABEL_PRINT_PAGE_SCHEMA.read_text(encoding="utf-8"))
		workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
		self.assertEqual(page["name"], "label-print-center")
		self.assertTrue(
			any(link.get("link_to") == "label-print-center" for link in workspace["links"])
		)


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

	def test_job_label_jinja_delimiters_are_balanced(self):
		for format_path in (
			JOB_TRAVELLER_FORMAT,
			JOB_FG_FORMAT,
			JOB_SUBPART_FORMAT,
			JOB_ALL_LABELS_FORMAT,
		):
			html = json.loads(format_path.read_text(encoding="utf-8"))["html"]
			with self.subTest(format=format_path.name):
				self.assertNotIn("%>", html)
				self.assertEqual(html.count("{%"), html.count("%}"))

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
