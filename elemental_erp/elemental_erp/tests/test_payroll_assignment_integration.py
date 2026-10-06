"""Exercise account repair without requiring a live Frappe database."""
import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).resolve().parents[2] / "utils" / "salary_package.py"


class TestPayrollAssignmentIntegration(unittest.TestCase):
	def setUp(self):
		self.frappe = Mock()
		self.frappe.db.get_value.side_effect = [1, "SSA-1"]
		self.package = SimpleNamespace(employee="EMP-1", effective_from=date(2026, 9, 1))
		tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
		function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "ensure_salary_structure_assignment")
		namespace = {"frappe": self.frappe, "getdate": lambda value: value, "ELEMENTAL_STRUCTURE_PREFIX": "Elemental Salary Package"}
		exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
		self.ensure = namespace[function.name]

	def test_blank_generated_account_is_repaired(self):
		self.frappe.get_doc.return_value = SimpleNamespace(salary_structure="Elemental Salary Package - EF", payroll_payable_account=None)
		self.assertEqual(self.ensure(self.package, "Payroll Payable - EF"), "SSA-1")
		self.frappe.db.set_value.assert_called_once_with("Salary Structure Assignment", "SSA-1", "payroll_payable_account", "Payroll Payable - EF", update_modified=True)

	def test_standard_assignment_is_preserved(self):
		self.frappe.get_doc.return_value = SimpleNamespace(salary_structure="Standard Staff", payroll_payable_account=None)
		self.ensure(self.package, "Payroll Payable - EF")
		self.frappe.db.set_value.assert_not_called()

	def test_matching_account_is_idempotent(self):
		self.frappe.get_doc.return_value = SimpleNamespace(salary_structure="Elemental Salary Package - EF", payroll_payable_account="Payroll Payable - EF")
		self.ensure(self.package, "Payroll Payable - EF")
		self.frappe.db.set_value.assert_not_called()

	def test_conflicting_account_is_reported_and_preserved(self):
		self.frappe.get_doc.return_value = SimpleNamespace(salary_structure="Elemental Salary Package - EF", payroll_payable_account="Other Payable")
		self.frappe.throw.side_effect = ValueError
		with self.assertRaises(ValueError):
			self.ensure(self.package, "Payroll Payable - EF")
		self.frappe.db.set_value.assert_not_called()

	def test_prompt_named_structure_receives_explicit_insert_name(self):
		tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
		function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_ensure_elemental_salary_structure")
		namespace = {"frappe": self.frappe, "ELEMENTAL_STRUCTURE_PREFIX": "Elemental Salary Package"}
		exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
		ensure_structure = namespace[function.name]
		self.frappe.db.exists.side_effect = [False, "Basic"]
		structure = Mock(docstatus=0)
		structure.name = "Elemental Salary Package - EF"
		self.frappe.new_doc.return_value = structure
		self.assertEqual(ensure_structure("EF", "INR"), "Elemental Salary Package - EF")
		structure.insert.assert_called_once_with(ignore_permissions=True, ignore_mandatory=True, set_name="Elemental Salary Package - EF")
		structure.submit.assert_called_once_with()
		self.frappe.db.exists.side_effect = None
		self.frappe.db.exists.return_value = True
		self.assertEqual(ensure_structure("EF", "INR"), "Elemental Salary Package - EF")
		self.assertEqual(structure.insert.call_count, 1)


if __name__ == "__main__":
	unittest.main()
