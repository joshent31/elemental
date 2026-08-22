"""Regression tests for Purchase Order initiation helpers."""

import json
import unittest
from pathlib import Path

from elemental_erp.utils.purchase import allocate_order_quantity


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "custom_field.json"


class TestAllocateOrderQuantity(unittest.TestCase):
	def test_allocates_oldest_rows_first(self):
		rows = [
			{"indent_item": "ROW-1", "bal_indent_qty": 2},
			{"indent_item": "ROW-2", "bal_indent_qty": 5},
		]

		allocations = allocate_order_quantity(rows, 6)

		self.assertEqual(
			[(row["indent_item"], row["po_qty"]) for row in allocations],
			[("ROW-1", 2), ("ROW-2", 4)],
		)

	def test_rejects_quantity_above_live_balance(self):
		with self.assertRaisesRegex(ValueError, "Only 3 is still outstanding"):
			allocate_order_quantity([{"bal_indent_qty": 3}], 4)

	def test_rejects_non_finite_and_non_positive_quantities(self):
		for quantity in (0, -1, float("inf"), float("nan")):
			with self.subTest(quantity=quantity):
				with self.assertRaises(ValueError):
					allocate_order_quantity([], quantity)


class TestPurchaseOrderLinkageFixture(unittest.TestCase):
	def test_purchase_order_item_tracks_exact_indent_line(self):
		fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
		fields = {
			(row.get("dt"), row.get("fieldname")): row
			for row in fixtures
			if row.get("doctype") == "Custom Field"
		}

		self.assertEqual(
			fields[("Purchase Order Item", "elemental_material_indent")]["options"],
			"Material Indent",
		)
		self.assertIn(("Purchase Order Item", "elemental_material_indent_item"), fields)


if __name__ == "__main__":
	unittest.main()
