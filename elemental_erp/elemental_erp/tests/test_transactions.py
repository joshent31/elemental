"""Regression tests for shared transaction invariants."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from elemental_erp.utils.transactions import (
    advance_job_status,
    assert_qr_belongs_to_job,
    positive_quantity,
)


class TestQuantityValidation(unittest.TestCase):
    def test_positive_quantity(self):
        self.assertEqual(positive_quantity("2.5"), 2.5)

    def test_rejects_zero_negative_and_non_finite(self):
        for value in (0, -1, "nan", "inf", None):
            with self.subTest(value=value):
                with self.assertRaises(frappe.ValidationError):
                    positive_quantity(value)


class TestJobTransitions(unittest.TestCase):
    def test_does_not_regress_job(self):
        with patch("frappe.db.get_value", return_value="In Packaging"):
            with patch("frappe.db.set_value") as set_value:
                result = advance_job_status("JOB-001", "In Production")
                self.assertEqual(result, "In Packaging")
                set_value.assert_not_called()

    def test_rejects_terminal_job(self):
        with patch("frappe.db.get_value", return_value="Cancelled"):
            with self.assertRaises(frappe.ValidationError):
                advance_job_status("JOB-001", "In Production")


class TestCrossJobLinkage(unittest.TestCase):
    def test_rejects_qr_from_another_job(self):
        qr = SimpleNamespace(
            name="QR-001",
            job="JOB-OTHER",
            finished_good="FG-001",
            total_qty=10,
            completed_qty=10,
            status="Completed",
            process_name="Packing",
        )
        with patch("frappe.db.get_value", return_value=qr):
            with self.assertRaises(frappe.ValidationError):
                assert_qr_belongs_to_job("QR-001", "JOB-001")
