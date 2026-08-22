"""Tests for QR Code Master status logic and Job auto-completion."""
import unittest
from unittest.mock import patch, MagicMock

import frappe


class TestQRCodeMasterUpdateStatus(unittest.TestCase):
    """Tests for QRCodeMaster.update_status()."""

    def _make_master(self, total_qty=100, completed_qty=0):
        """Create a mock QR Code Master with given quantities."""
        from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import QRCodeMaster

        doc = MagicMock(spec=QRCodeMaster)
        doc.total_qty = total_qty
        doc.completed_qty = completed_qty
        doc.subpart_name = "Chair Leg"
        doc.process_name = "Metal"
        doc.job = "JOB-001"
        doc.update_status = QRCodeMaster.update_status.__get__(doc, QRCodeMaster)
        return doc

    def test_scan_advances_progress(self):
        """Scanning valid qty advances completed_qty and sets In Process."""
        doc = self._make_master(total_qty=100, completed_qty=0)
        with patch("frappe.db.count", return_value=5):
            doc.update_status(25)
            self.assertEqual(doc.completed_qty, 25)
            self.assertEqual(doc.status, "In Process")
            doc.save.assert_called_once_with(ignore_permissions=True)

    def test_scan_completes_when_full(self):
        """Scanning remaining qty marks status as Completed."""
        doc = self._make_master(total_qty=100, completed_qty=90)
        with patch("frappe.db.count", return_value=5):
            doc.update_status(10)
            self.assertEqual(doc.completed_qty, 100)
            self.assertEqual(doc.status, "Completed")

    def test_scan_over_limit_throws(self):
        """Scanning more than remaining qty throws an error."""
        doc = self._make_master(total_qty=100, completed_qty=95)
        with self.assertRaises(frappe.ValidationError):
            doc.update_status(10)  # only 5 remaining

    def test_scan_zero_is_rejected(self):
        """Public scan quantities must be strictly positive."""
        doc = self._make_master(total_qty=100, completed_qty=0)
        with self.assertRaises(frappe.ValidationError):
            doc.update_status(0)

    def test_over_scan_boundary(self):
        """A quantity beyond the 1e-6 tolerance is rejected."""
        doc = self._make_master(total_qty=100, completed_qty=99.9)
        with self.assertRaises(frappe.ValidationError):
            doc.update_status(0.2)


class TestJobAutoCompletion(unittest.TestCase):
    """Tests for check_job_fully_completed()."""

    def test_all_qr_completed_flips_job(self):
        """When no pending QRs remain, Job status flips to In Packaging."""
        from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import check_job_fully_completed

        with patch("frappe.db.count", return_value=0):
            with patch("frappe.db.get_value", return_value="In Production"):
                with patch("frappe.db.set_value") as mock_set:
                    with patch("frappe.db.sql"):
                        check_job_fully_completed("JOB-001")
                        mock_set.assert_called_once_with("Job", "JOB-001", "status", "In Packaging")

    def test_pending_qr_remains(self):
        """When QRs are still pending, Job status is NOT changed."""
        from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import check_job_fully_completed

        with patch("frappe.db.count", return_value=3):
            with patch("frappe.db.set_value") as mock_set:
                check_job_fully_completed("JOB-001")
                mock_set.assert_not_called()


class TestCreateQRMaster(unittest.TestCase):
    """Tests for create_qr_master() factory function."""

    def test_creates_doc_with_qr_image(self):
        from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import create_qr_master

        mock_doc = MagicMock()
        mock_doc.name = "QRC-001"

        with patch("frappe.generate_hash", return_value="HASH123"):
            with patch("frappe.utils.get_url", return_value="https://example.com/qr/HASH123"):
                with patch("elemental_erp.utils.qr_generator.generate_qr_image", return_value="/files/HASH123.png"):
                    with patch("frappe.get_doc", return_value=mock_doc):
                        result = create_qr_master(
                            job="JOB-001", finished_good="FG-001",
                            subpart_code="SP-01", subpart_name="Leg",
                            process_name="Metal", total_qty=50,
                        )
                        # Verify doc was configured correctly
                        args = mock_doc.insert.call_args
                        self.assertTrue(args[1].get("ignore_permissions") or args[0][0].get("ignore_permissions"))
