"""Standalone regressions for Job-first scanning and visible box contents."""

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
PAGES = APP_ROOT / "templates" / "pages"


class TestJobQrSchema(unittest.TestCase):
	def test_job_has_one_unique_qr_and_printable_label(self):
		job = json.loads(
			(APP_ROOT / "elemental_erp" / "doctype" / "job" / "job.json").read_text(
				encoding="utf-8"
			)
		)
		fields = {row["fieldname"]: row for row in job["fields"] if row.get("fieldname")}
		self.assertEqual(fields["job_qr_value"]["unique"], 1)
		self.assertEqual(fields["job_qr_image"]["fieldtype"], "Attach Image")

		label = json.loads(
			(
				APP_ROOT
				/ "elemental_erp"
				/ "print_format"
				/ "job_qr_label"
				/ "job_qr_label.json"
			).read_text(encoding="utf-8")
		)
		self.assertIn("doc.job_qr_image", label["html"])
		self.assertIn("doc.name", label["html"])

	def test_existing_jobs_are_backfilled_after_migrate(self):
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		setup = (APP_ROOT / "setup.py").read_text(encoding="utf-8")
		self.assertIn("backfill_job_qr_codes", hooks)
		self.assertIn("ensure_job_qr(job_name)", setup)


class TestJobFirstScanPages(unittest.TestCase):
	def test_department_pages_are_locked_until_job_activation(self):
		for filename, scan_button, job_argument in (
			("process_scan.html", 'id="start-scan"', "job: jobContext.name"),
			("transfer_out.html", 'id="start-scan-out"', "job: jobContext.name"),
			("transfer_in.html", 'id="start-scan-in"', "job: jobContext.name"),
			("dispatch_scan.html", 'id="start-dispatch-btn"', "job: currentJob"),
		):
			with self.subTest(page=filename):
				html = (PAGES / filename).read_text(encoding="utf-8")
				self.assertIn("job_scan_context.js", html)
				self.assertIn(scan_button, html)
				self.assertIn("disabled", html)
				self.assertIn(job_argument, html)

	def test_server_rejects_cross_job_context(self):
		api = (APP_ROOT / "api.py").read_text(encoding="utf-8")
		self.assertIn("def _require_job_context(job_code, actual_job):", api)
		self.assertIn("if job.name != actual_job:", api)
		self.assertIn("Stop and scan the correct Job QR", api)
		for signature in (
			"def complete_subpart_process(",
			"def create_transfer(",
			"def receive_transfer(",
			"def map_part_to_box(",
			"def scan_box_dispatch(",
		):
			self.assertIn(signature, api)


class TestPackingBoxContents(unittest.TestCase):
	def test_box_rows_support_subparts_and_finished_goods(self):
		schema = json.loads(
			(
				APP_ROOT
				/ "elemental_erp"
				/ "doctype"
				/ "packing_box_content"
				/ "packing_box_content.json"
			).read_text(encoding="utf-8")
		)
		fields = {row["fieldname"]: row for row in schema["fields"]}
		self.assertEqual(fields["finished_good"]["options"], "Finished Good")
		self.assertEqual(fields["qc_inspection"]["options"], "QC Inspection")
		self.assertIn("Finished Good", fields["content_type"]["options"])

	def test_scanned_box_view_renders_diagrams_and_quantities(self):
		for filename in ("pack_box.html", "site_scan.html"):
			with self.subTest(page=filename):
				html = (PAGES / filename).read_text(encoding="utf-8")
				self.assertIn("content.diagram", html)
				self.assertIn("content.packed_qty", html)
				self.assertIn("Material Inside This Box", html)

		api = (APP_ROOT / "api.py").read_text(encoding="utf-8")
		self.assertIn('"diagram": fg.get("fg_image")', api)
		self.assertIn('"diagram": label.get("ref_image")', api)
		self.assertIn('"content_type": "Finished Good"', api)


if __name__ == "__main__":
	unittest.main()
