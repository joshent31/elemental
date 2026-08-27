"""Static regression tests for employee-specific salary packages."""

import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = APP_ROOT / "elemental_erp" / "doctype"


class TestSalaryPackages(unittest.TestCase):
	def load_doctype(self, folder):
		path = DOCTYPE_ROOT / folder / f"{folder}.json"
		return json.loads(path.read_text(encoding="utf-8"))

	def test_package_is_submittable_and_component_driven(self):
		package = self.load_doctype("employee_salary_package")
		fields = {row.get("fieldname"): row for row in package["fields"]}
		self.assertEqual(package["is_submittable"], 1)
		self.assertEqual(fields["components"]["options"], "Salary Package Component")
		self.assertIn("effective_from", fields)
		self.assertIn("annual_ctc", fields)

		component = self.load_doctype("salary_package_component")
		component_fields = {row.get("fieldname"): row for row in component["fields"]}
		self.assertEqual(component["istable"], 1)
		self.assertIn("Employer Contribution", component_fields["treatment"]["options"])
		self.assertIn("Annual", component_fields["amount_basis"]["options"])

	def test_annual_revision_generates_one_package_per_employee(self):
		revision = self.load_doctype("annual_salary_revision")
		self.assertEqual(revision["is_submittable"], 1)
		controller = (DOCTYPE_ROOT / "annual_salary_revision" / "annual_salary_revision.py").read_text(encoding="utf-8")
		self.assertIn("by_employee = defaultdict(list)", controller)
		self.assertIn('frappe.new_doc("Employee Salary Package")', controller)
		self.assertIn("package.submit()", controller)
		self.assertIn("row.monthly_amount = flt(row.annual_amount / 12, 6)", controller)

	def test_payroll_entry_is_not_overridden_and_package_is_opt_in(self):
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn('"before_validate": "elemental_erp.utils.salary_package.apply_employee_salary_package"', hooks)
		self.assertNotIn("override_doctype_class", hooks)
		integration = (APP_ROOT / "utils" / "salary_package.py").read_text(encoding="utf-8")
		self.assertIn('"use_elemental_salary_package"', integration)
		self.assertIn('doc.elemental_salary_package = package.name', integration)
		self.assertIn("doc.get_emp_and_working_day_details()", integration)
		self.assertIn('_set_component_amount(doc, "earnings", "Overtime"', integration)
		self.assertNotIn('frappe.new_doc("Salary Slip")', integration)

	def test_salary_history_cannot_be_cancelled_after_submitted_payroll(self):
		package = (DOCTYPE_ROOT / "employee_salary_package" / "employee_salary_package.py").read_text(encoding="utf-8")
		revision = (DOCTYPE_ROOT / "annual_salary_revision" / "annual_salary_revision.py").read_text(encoding="utf-8")
		self.assertIn('"Salary Slip", {"elemental_salary_package": self.name, "docstatus": ["!=", 2]}', package)
		self.assertIn('"elemental_salary_package": ["in", list(packages)]', revision)

	def test_employee_and_salary_slip_have_auditable_package_fields(self):
		fixtures = json.loads((APP_ROOT / "fixtures" / "custom_field.json").read_text(encoding="utf-8"))
		fields = {(row["dt"], row["fieldname"]): row for row in fixtures}
		self.assertEqual(fields[("Employee", "use_elemental_salary_package")]["read_only"], 1)
		self.assertEqual(fields[("Salary Slip", "elemental_salary_package")]["options"], "Employee Salary Package")
		client = (APP_ROOT / "public" / "js" / "employee.js").read_text(encoding="utf-8")
		self.assertIn('__("New Salary Package")', client)
		self.assertIn('__("View Salary Packages")', client)

	def test_package_client_preview_keeps_exact_annual_basis(self):
		client = (APP_ROOT / "public" / "js" / "salary_package.js").read_text(encoding="utf-8")
		self.assertIn('row.amount_basis === "Annual"', client)
		self.assertIn('flt(row.annual_amount) / 12', client)
		self.assertIn('totals.Earning - totals.Deduction', client)

	def test_worker_ot_uses_effective_package_gross_with_rollout_fallback(self):
		overtime = (APP_ROOT / "utils" / "worker_overtime.py").read_text(encoding="utf-8")
		self.assertIn("def get_monthly_fixed_salary", overtime)
		self.assertIn('"Employee Salary Package"', overtime)
		self.assertIn('"monthly_earnings"', overtime)
		self.assertIn("return fallback_ctc", overtime)


if __name__ == "__main__":
	unittest.main()
