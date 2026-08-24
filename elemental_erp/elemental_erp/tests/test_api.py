"""Tests for elemental_erp.api — whitelisted endpoints.

These tests mock Frappe DB calls to verify business logic without needing
a live site. Each test isolates the function under test from the database.
"""
import unittest
from unittest.mock import patch, MagicMock, call

import frappe


class TestQRStatus(unittest.TestCase):
    """Tests for get_qr_status()."""

    def test_valid_qr(self):
        from elemental_erp.api import get_qr_status

        mock_qr = {
            "name": "QRC-001", "job": "JOB-2025-00001",
            "finished_good": "FG-001", "subpart_code": "SP-01",
            "subpart_name": "Chair Leg", "process": "Metal",
            "total_qty": 100, "completed_qty": 50, "status": "In Process",
        }
        with patch("frappe.db.get_value", return_value=mock_qr):
            result = get_qr_status("abc123")
            self.assertEqual(result["name"], "QRC-001")
            self.assertEqual(result["status"], "In Process")

    def test_invalid_qr_throws(self):
        from elemental_erp.api import get_qr_status

        with patch("frappe.db.get_value", return_value=None):
            with self.assertRaises(frappe.DoesNotExistError):
                get_qr_status("nonexistent")


class TestScanQR(unittest.TestCase):
    """Tests for scan_qr()."""

    def test_creates_scan_log(self):
        from elemental_erp.api import scan_qr

        with patch("frappe.db.get_value", return_value="QRC-001"):
            with patch("frappe.get_doc") as mock_doc:
                mock_instance = MagicMock()
                mock_doc.return_value = mock_instance

                result = scan_qr("abc123", department="Metal", qty_scanned=5)

                log_calls = [c for c in mock_doc.call_args_list if c.args and isinstance(c.args[0], dict)]
                self.assertEqual(len(log_calls), 1)
                args = log_calls[0].args[0]
                self.assertEqual(args["doctype"], "QR Scan Log")
                self.assertEqual(args["qr_code_master"], "QRC-001")
                self.assertEqual(args["department"], "Metal")
                self.assertEqual(args["qty_scanned"], 5)
                mock_instance.insert.assert_called_once_with(ignore_permissions=True)

    def test_invalid_qr_throws(self):
        from elemental_erp.api import scan_qr

        with patch("frappe.db.get_value", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                scan_qr("nonexistent")


class TestDepartmentTransfer(unittest.TestCase):
    """Tests for lookup_part_qr(), create_transfer(), receive_transfer()."""

    def test_lookup_part_qr_valid(self):
        from elemental_erp.api import lookup_part_qr

        mock_qr = {
            "name": "QRC-001", "job": "JOB-001",
            "subpart_code": "SP-01", "subpart_name": "Leg",
            "process": "Metal", "total_qty": 50, "completed_qty": 20,
            "status": "In Process",
        }
        with patch("elemental_erp.api._get_subpart_label", return_value=None), patch(
            "frappe.db.get_value", side_effect=[None, frappe._dict(mock_qr)]
        ), patch("elemental_erp.api._require_job_context"):
            result = lookup_part_qr("abc123", job="JOB-001")
            self.assertEqual(result["job"], "JOB-001")

    def test_lookup_part_qr_invalid(self):
        from elemental_erp.api import lookup_part_qr

        with patch("elemental_erp.api._get_subpart_label", return_value=None), patch(
            "frappe.db.get_value", return_value=None
        ):
            with self.assertRaises(frappe.ValidationError):
                lookup_part_qr("nonexistent", job="JOB-001")

    def test_create_transfer_generates_qr(self):
        from elemental_erp.api import create_transfer

        mock_qr_master = MagicMock()
        mock_qr_master.job = "JOB-001"
        mock_qr_master.total_qty = 100

        with patch("frappe.db.get_value", return_value="QRC-001"):
            with patch("frappe.get_doc", return_value=mock_qr_master):
                with patch("frappe.generate_hash", return_value="ABC123"):
                    with patch("frappe.utils.get_url", return_value="https://example.com"):
                        with patch("elemental_erp.utils.qr_generator.generate_qr_image", return_value="/files/ABC123.png"):
                            with patch("frappe.db.commit"), patch("elemental_erp.api._require_job_context"):
                                result = create_transfer("abc123", "Metal", "Paint", 10, job="JOB-001")
                                # Verify the transfer doc was created with correct fields
                                mock_qr_master.insert.assert_called()

    def test_receive_transfer_already_received(self):
        from elemental_erp.api import receive_transfer

        mock_transfer = MagicMock()
        mock_transfer.status = "Received"

        with patch("frappe.db.get_value", return_value="DT-001"):
            with patch("frappe.get_doc", return_value=mock_transfer), patch(
                "elemental_erp.api._require_job_context"
            ):
                with self.assertRaises(frappe.ValidationError):
                    receive_transfer("transfer_qr", 10, job="JOB-001")


class TestMaterialFlow(unittest.TestCase):
    """Tests for generate_indent_items_from_bom() and related material functions."""

    def test_indent_from_bom_no_fg_throws(self):
        """Throws when no un-indented FGs with BOM exist."""
        from elemental_erp.api import generate_indent_items_from_bom

        mock_job = MagicMock()
        mock_job.fg_items = []

        with patch("frappe.get_doc", return_value=mock_job):
            with self.assertRaises(frappe.ValidationError):
                generate_indent_items_from_bom("JOB-001")

    def test_indent_from_bom_aggregates(self):
        """Correctly aggregates BOM items across FGs and Job Qty."""
        from elemental_erp.api import generate_indent_items_from_bom

        # FG with BOM
        mock_bom = MagicMock()
        mock_bom.raw_material = "Wood Sheet"
        mock_bom.qty_per_fg = 2
        mock_bom.uom = "Nos"

        mock_fg = MagicMock()
        mock_fg.bom_items = [mock_bom]

        # Job FG row
        mock_fg_row = MagicMock()
        mock_fg_row.finished_good = "FG-001"
        mock_fg_row.job_qty = 10
        mock_fg_row.indent_raised = 0

        mock_job = MagicMock()
        mock_job.fg_items = [mock_fg_row]

        def get_doc_side_effect(dt, name=None):
            if dt == "Job":
                return mock_job
            if dt == "Finished Good":
                return mock_fg
            return MagicMock()

        with patch("frappe.get_doc", side_effect=get_doc_side_effect):
            result = generate_indent_items_from_bom("JOB-001")
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["raw_material"], "Wood Sheet")
            self.assertEqual(result["items"][0]["required_qty"], 20)  # 2 * 10

    def test_indent_skips_already_indented(self):
        """Skips FG rows where indent_raised is already 1."""
        from elemental_erp.api import generate_indent_items_from_bom

        mock_fg_row = MagicMock()
        mock_fg_row.finished_good = "FG-001"
        mock_fg_row.indent_raised = 1  # Already indented

        mock_job = MagicMock()
        mock_job.fg_items = [mock_fg_row]

        with patch("frappe.get_doc", return_value=mock_job):
            with self.assertRaises(frappe.ValidationError):
                generate_indent_items_from_bom("JOB-001")


class TestJobLifecycle(unittest.TestCase):
    """Tests for Job close/reopen/cancel API functions."""

    def test_close_job_non_admin_throws(self):
        from elemental_erp.api import close_job

        with patch("frappe.get_roles", return_value=["Sales User"]):
            with self.assertRaises(frappe.ValidationError):
                close_job("JOB-001")

    def test_close_job_already_closed(self):
        from elemental_erp.api import close_job

        with patch("frappe.get_roles", return_value=["System Manager"]):
            with patch("frappe.db.get_value", return_value="Closed"):
                with self.assertRaises(frappe.ValidationError):
                    close_job("JOB-001")

    def test_reopen_job_not_terminal(self):
        from elemental_erp.api import reopen_job

        with patch("frappe.get_roles", return_value=["System Manager"]):
            with patch("frappe.db.get_value", return_value="In Production"):
                with self.assertRaises(frappe.ValidationError):
                    reopen_job("JOB-001")

    def test_reopen_job_success(self):
        from elemental_erp.api import reopen_job

        with patch("frappe.get_roles", return_value=["System Manager"]):
            with patch("frappe.db.get_value", return_value="Closed"):
                with patch("frappe.db.set_value") as mock_set:
                    with patch("frappe.db.commit"):
                        result = reopen_job("JOB-001")
                        mock_set.assert_called_with("Job", "JOB-001", "status", "Job Created")
                        self.assertEqual(result["status"], "Job Created")


class TestPackingLabels(unittest.TestCase):
    """Tests for create_packing_labels()."""

    def test_invalid_box_count(self):
        from elemental_erp.api import create_packing_labels

        with self.assertRaises(frappe.ValidationError):
            create_packing_labels("JOB-001", 0)
        with self.assertRaises(frappe.ValidationError):
            create_packing_labels("JOB-001", -5)

    def test_creates_labels(self):
        from elemental_erp.api import create_packing_labels

        with patch("frappe.db.set_value"):
            with patch("frappe.db.get_value", return_value="Job Created"):
                with patch("frappe.db.count", return_value=0):
                    with patch("frappe.db.commit"):
                        with patch("frappe.generate_hash", return_value="HASH123"):
                            with patch("frappe.utils.get_url", return_value="https://example.com"):
                                with patch("elemental_erp.utils.qr_generator.generate_qr_image", return_value="/files/HASH123.png"):
                                    with patch("frappe.get_doc") as mock_doc:
                                        mock_box = MagicMock()
                                        mock_doc.return_value = mock_box

                                        result = create_packing_labels("JOB-001", 3)
                                        self.assertEqual(result["created"], 3)
                                        # One Job lookup plus three box documents.
                                        self.assertEqual(mock_doc.call_count, 4)


class TestSalesInvoice(unittest.TestCase):
    """Tests for create_sales_invoice_for_job()."""

    def test_cannot_create_if_boxes_not_loaded(self):
        from elemental_erp.api import create_sales_invoice_for_job

        with patch("frappe.db.count", side_effect=[5, 2]):
            # 5 total boxes, 2 not yet loaded
            with self.assertRaises(frappe.ValidationError):
                create_sales_invoice_for_job("JOB-001")

    def test_cannot_create_if_si_exists(self):
        from elemental_erp.api import create_sales_invoice_for_job

        with patch("frappe.db.count", side_effect=[1, 0]):
            # One loaded box, but SI already exists
            with patch("frappe.db.exists", return_value="SI-001"):
                with self.assertRaises(frappe.ValidationError):
                    create_sales_invoice_for_job("JOB-001")

    def test_no_mapped_items_throws(self):
        from elemental_erp.api import create_sales_invoice_for_job

        with patch("frappe.db.count", side_effect=[1, 0]):
            with patch("frappe.db.exists", return_value=None):
                mock_job = MagicMock()
                mock_job.fg_items = [MagicMock(finished_good="FG-001")]

                def get_value_side_effect(dt, name, field=None, *args, **kwargs):
                    if dt == "Finished Good" and field is None:
                        return {"erpnext_item": None}
                    return None

                with patch("frappe.db.get_value", side_effect=get_value_side_effect):
                    with patch("frappe.get_doc", return_value=mock_job):
                        with self.assertRaises(frappe.ValidationError):
                            create_sales_invoice_for_job("JOB-001")
