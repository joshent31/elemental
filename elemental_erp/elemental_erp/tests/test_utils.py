"""Tests for elemental_erp utility modules."""
import unittest
from unittest.mock import patch, MagicMock

import frappe


class TestCosting(unittest.TestCase):
    """Tests for elemental_erp.utils.costing module."""

    def test_hourly_rate_no_employee(self):
        """hourly_rate returns 0 when no employee is passed."""
        from elemental_erp.utils.costing import hourly_rate
        self.assertEqual(hourly_rate(None), 0)
        self.assertEqual(hourly_rate(""), 0)

    def test_hourly_rate_with_ctc(self):
        """hourly_rate computes CTC / 208 when employee has a CTC set."""
        from elemental_erp.utils.costing import hourly_rate

        with patch("frappe.db.get_value") as mock_get:
            mock_get.return_value = 500000  # CTC of 5,00,000
            rate = hourly_rate("EMP-001")
            self.assertAlmostEqual(rate, 500000 / 208, places=2)

    def test_hourly_rate_no_ctc(self):
        """hourly_rate returns 0 when employee exists but CTC is None."""
        from elemental_erp.utils.costing import hourly_rate

        with patch("frappe.db.get_value") as mock_get:
            mock_get.return_value = None
            rate = hourly_rate("EMP-001")
            self.assertEqual(rate, 0)

    def test_compute_cost_basic(self):
        """compute_cost multiplies hourly rate by hours."""
        from elemental_erp.utils.costing import compute_cost

        with patch("elemental_erp.utils.costing.hourly_rate", return_value=250):
            cost = compute_cost("EMP-001", 8)
            self.assertAlmostEqual(cost, 250 * 8, places=2)

    def test_compute_cost_zero_hours(self):
        """compute_cost returns 0 when hours is 0 or None."""
        from elemental_erp.utils.costing import compute_cost

        with patch("elemental_erp.utils.costing.hourly_rate", return_value=250):
            self.assertEqual(compute_cost("EMP-001", 0), 0)
            self.assertEqual(compute_cost("EMP-001", None), 0)

    def test_compute_cost_no_employee(self):
        """compute_cost returns 0 when no employee."""
        from elemental_erp.utils.costing import compute_cost
        self.assertEqual(compute_cost(None, 8), 0)


class TestQRGenerator(unittest.TestCase):
    """Tests for elemental_erp.utils.qr_generator module."""

    def test_generate_qr_image_creates_file(self):
        """generate_qr_image creates a file and returns file_url."""
        from elemental_erp.utils.qr_generator import generate_qr_image

        mock_file_doc = MagicMock()
        mock_file_doc.file_url = "/files/TEST123.png"

        with patch("elemental_erp.utils.qr_generator.save_file", return_value=mock_file_doc):
            with patch("elemental_erp.utils.qr_generator.qrcode.make") as mock_make:
                mock_img = MagicMock()
                mock_make.return_value = mock_img

                result = generate_qr_image(
                    "TEST123", "https://example.com/qr/TEST123",
                    "QR Code Master", "QRC-001"
                )
                self.assertEqual(result, "/files/TEST123.png")
                mock_make.assert_called_once_with("https://example.com/qr/TEST123")
