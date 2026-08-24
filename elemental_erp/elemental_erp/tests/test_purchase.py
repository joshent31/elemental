"""Regression tests for Purchase Order initiation helpers."""

import json
import unittest
from pathlib import Path

from elemental_erp.utils.purchase import allocate_order_quantity


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "custom_field.json"
APP_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_INDENT_CONTROLLER = (
	APP_ROOT / "elemental_erp" / "doctype" / "material_indent" / "material_indent.py"
)
MATERIAL_INDENT_CLIENT = APP_ROOT / "public" / "js" / "material_indent.js"
HOOKS_PATH = APP_ROOT / "hooks.py"


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

	def test_manual_purchase_order_header_links_are_editable(self):
		fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
		fields = {
			(row.get("dt"), row.get("fieldname")): row
			for row in fixtures
			if row.get("doctype") == "Custom Field"
		}

		for fieldname in ("elemental_job", "elemental_material_indent"):
			with self.subTest(fieldname=fieldname):
				field = fields[("Purchase Order", fieldname)]
				self.assertFalse(field.get("read_only"))
		self.assertFalse(fields[("Purchase Order", "elemental_material_indent")].get("unique"))


class TestMaterialIndentPurchaseHandoff(unittest.TestCase):
	def test_submit_does_not_create_purchase_order(self):
		controller = MATERIAL_INDENT_CONTROLLER.read_text(encoding="utf-8")
		on_submit = controller.split("def on_submit", 1)[1].split("def ", 1)[0]
		self.assertNotIn("_create_po_from_indent_doc", controller)
		self.assertNotIn('frappe.get_doc("Purchase Order"', on_submit)
		self.assertNotIn(".insert(", on_submit)

	def test_only_purchase_actions_are_exposed_after_submit(self):
		client = MATERIAL_INDENT_CLIENT.read_text(encoding="utf-8")
		self.assertNotIn("create_purchase_order_from_indent", client)
		self.assertIn('"Elemental Purchase User"', client)
		self.assertIn('"Open PO Initiation"', client)
		self.assertIn('"New Purchase Order"', client)

	def test_standard_purchase_order_has_server_side_linkage_hooks(self):
		hooks = HOOKS_PATH.read_text(encoding="utf-8")
		self.assertIn('"Purchase Order": {', hooks)
		self.assertIn("validate_material_indent_linkage", hooks)
		self.assertIn("mark_material_indents_in_purchase", hooks)


if __name__ == "__main__":
	unittest.main()
