"""Regression tests for the shared Job subpart traveller label workflow."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe


APP_ROOT = Path(__file__).resolve().parents[2]


class TestJobSubpartLabelSchema(unittest.TestCase):
	def test_standard_job_print_reconciles_late_subparts(self):
		job_controller = (
			APP_ROOT / "elemental_erp" / "doctype" / "job" / "job.py"
		).read_text(encoding="utf-8")
		self.assertIn("def before_print(", job_controller)
		self.assertIn("reconcile_job_subpart_trackers(self.name)", job_controller)

	def test_label_is_job_specific_and_has_one_unique_qr(self):
		doctype = json.loads(
			(
				APP_ROOT
				/ "elemental_erp"
				/ "doctype"
				/ "job_subpart_label"
				/ "job_subpart_label.json"
			).read_text(encoding="utf-8")
		)
		fields = {field["fieldname"]: field for field in doctype["fields"] if field.get("fieldname")}
		self.assertEqual(fields["job"]["options"], "Job")
		self.assertEqual(fields["finished_good"]["options"], "Finished Good")
		self.assertEqual(fields["processes"]["options"], "Job Subpart Label Process")
		self.assertEqual(fields["qr_value"]["unique"], 1)

	def test_parent_and_child_doctypes_have_importable_controller_files(self):
		for doctype_name in ("job_subpart_label", "job_subpart_label_process"):
			with self.subTest(doctype=doctype_name):
				controller = (
					APP_ROOT
					/ "elemental_erp"
					/ "doctype"
					/ doctype_name
					/ f"{doctype_name}.py"
				)
				self.assertTrue(controller.exists())

	def test_box_content_links_the_shared_label(self):
		doctype = json.loads(
			(
				APP_ROOT
				/ "elemental_erp"
				/ "doctype"
				/ "packing_box_content"
				/ "packing_box_content.json"
			).read_text(encoding="utf-8")
		)
		fields = {field["fieldname"]: field for field in doctype["fields"]}
		self.assertEqual(fields["job_subpart_label"]["options"], "Job Subpart Label")
		self.assertNotIn("reqd", fields["qr_code_master"])

	def test_job_traveller_print_contains_qr_diagram_and_process_flow(self):
		print_format = json.loads(
			(
				APP_ROOT
				/ "elemental_erp"
				/ "print_format"
				/ "job_production_traveller"
				/ "job_production_traveller.json"
			).read_text(encoding="utf-8")
		)
		html = print_format["html"]
		self.assertEqual(print_format["doc_type"], "Job")
		self.assertIn("Job Subpart Label", html)
		self.assertIn("qr_image", html)
		self.assertIn("ref_image", html)
		self.assertIn("process.process_name", html)


class TestOrderedProcessCompletion(unittest.TestCase):
	def setUp(self):
		self.label = frappe._dict(
			{
				"name": "JSL-2026-00001",
				"job": "JOB-2026-00001",
				"finished_good": "FG-001",
				"subpart_code": "SP-001",
			}
		)
		self.processes = [
			frappe._dict(
				{
					"process_name": "Metal",
					"qr_code_master": "QR-METAL",
					"total_qty": 10,
					"completed_qty": 3,
					"status": "In Process",
				}
			),
			frappe._dict(
				{
					"process_name": "Powdercoating",
					"qr_code_master": "QR-POWDER",
					"total_qty": 10,
					"completed_qty": 1,
					"status": "In Process",
				}
			),
		]

	def test_downstream_quantity_cannot_exceed_previous_process(self):
		from elemental_erp.api import complete_subpart_process

		with patch("elemental_erp.api._require_roles"), patch(
			"elemental_erp.api._get_subpart_label", return_value=self.label
		), patch("elemental_erp.api._get_label_processes", return_value=self.processes), patch(
			"elemental_erp.api.require_doc_permission"
		), patch("elemental_erp.api.assert_active_job"), patch(
			"elemental_erp.api._lock_subpart_label"
		), patch("frappe.get_doc", return_value=MagicMock()):
			with self.assertRaises(frappe.ValidationError):
				complete_subpart_process("LABELQR", "Powdercoating", 3)

	def test_valid_completion_creates_a_scan_log_for_linked_tracker(self):
		from elemental_erp.api import complete_subpart_process

		label_doc = MagicMock()
		qr_doc = MagicMock(name="QR-POWDER")
		log_doc = MagicMock()

		def get_doc(doctype, name=None):
			if isinstance(doctype, dict):
				self.assertEqual(doctype["qr_code_master"], "QR-POWDER")
				self.assertEqual(doctype["department"], "Powdercoating")
				self.assertEqual(doctype["qty_scanned"], 2)
				return log_doc
			return label_doc if doctype == "Job Subpart Label" else qr_doc

		with patch("elemental_erp.api._require_roles"), patch(
			"elemental_erp.api._get_subpart_label", return_value=self.label
		), patch("elemental_erp.api._get_label_processes", return_value=self.processes), patch(
			"elemental_erp.api.require_doc_permission"
		), patch("elemental_erp.api.assert_active_job"), patch(
			"elemental_erp.api._lock_subpart_label"
		), patch("frappe.get_doc", side_effect=get_doc), patch(
			"frappe.db.commit"
		), patch("elemental_erp.api._subpart_label_status", return_value={"status": "In Process"}):
			result = complete_subpart_process("LABELQR", "Powdercoating", 2)

		log_doc.insert.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(result["status"], "In Process")

	def test_packing_process_cannot_be_completed_without_a_box(self):
		from elemental_erp.api import complete_subpart_process

		with patch("elemental_erp.api._require_roles"), patch(
			"elemental_erp.api._get_subpart_label", return_value=self.label
		):
			with self.assertRaises(frappe.ValidationError):
				complete_subpart_process("LABELQR", "Packing", 1)


class TestPackingSharedLabel(unittest.TestCase):
	def test_incomplete_production_is_rejected_before_box_mapping(self):
		from elemental_erp.api import map_part_to_box

		label = frappe._dict(
			{
				"name": "JSL-001",
				"job": "JOB-001",
				"finished_good": "FG-001",
				"subpart_name": "Leg",
				"total_qty": 10,
			}
		)
		processes = [
			frappe._dict(
				{
					"process_name": "Metal",
					"status": "In Process",
					"total_qty": 10,
					"completed_qty": 5,
				}
			)
		]
		with patch("elemental_erp.api._require_roles"), patch(
			"frappe.db.get_value", return_value="BOX-001"
		), patch("elemental_erp.api._get_subpart_label", return_value=label), patch(
			"elemental_erp.api._lock_subpart_label"
		), patch("elemental_erp.api._get_label_processes", return_value=processes):
			with self.assertRaises(frappe.ValidationError):
				map_part_to_box("BOXQR", "LABELQR", 1)
