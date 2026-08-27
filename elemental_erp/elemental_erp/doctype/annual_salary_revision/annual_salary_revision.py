from collections import defaultdict

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from elemental_erp.elemental_erp.doctype.employee_salary_package.employee_salary_package import PACKAGE_TREATMENTS


class AnnualSalaryRevision(Document):
	def validate(self):
		if not self.components:
			frappe.throw("Add or import at least one employee salary component.")
		seen = set()
		employees = {}
		for row in self.components:
			if not row.employee:
				frappe.throw(f"Employee is required in row {row.idx}.")
			key = (row.employee, row.salary_component, row.treatment)
			if key in seen:
				frappe.throw(f"{row.salary_component} is repeated for {row.employee} under {row.treatment}.")
			seen.add(key)
			if row.treatment not in PACKAGE_TREATMENTS:
				frappe.throw(f"Select a valid treatment in row {row.idx}.")
			employee = employees.get(row.employee)
			if not employee:
				employee = frappe.db.get_value("Employee", row.employee, ["status", "company"], as_dict=True)
				employees[row.employee] = employee
			if not employee or employee.status != "Active":
				frappe.throw(f"Employee {row.employee} is not active.")
			if employee.company != self.company:
				frappe.throw(f"Employee {row.employee} belongs to {employee.company}, not {self.company}.")
			component_type = frappe.db.get_value("Salary Component", row.salary_component, "type")
			if not component_type:
				frappe.throw(f"Salary Component {row.salary_component} does not exist.")
			if row.treatment != "Employer Contribution" and component_type != row.treatment:
				frappe.throw(f"{row.salary_component} is a {component_type}, not a {row.treatment}.")
			if row.amount_basis == "Annual":
				row.annual_amount = flt(row.annual_amount, 2)
				row.monthly_amount = flt(row.annual_amount / 12, 6)
			else:
				row.amount_basis = "Monthly"
				row.monthly_amount = flt(row.monthly_amount, 6)
				row.annual_amount = flt(row.monthly_amount * 12, 2)
			if row.monthly_amount < 0 or row.annual_amount < 0:
				frappe.throw(f"Amounts cannot be negative in row {row.idx}.")

	def before_submit(self):
		by_employee = defaultdict(list)
		for row in self.components:
			by_employee[row.employee].append(row)
		for employee, rows in by_employee.items():
			if frappe.db.exists(
				"Employee Salary Package",
				{"employee": employee, "effective_from": self.effective_from, "docstatus": 1},
			):
				frappe.throw(f"A submitted salary package already exists for {employee} from {self.effective_from}.")
			package = frappe.new_doc("Employee Salary Package")
			package.employee = employee
			package.effective_from = self.effective_from
			package.currency = self.currency
			package.annual_revision = self.name
			package.notes = self.notes
			for row in rows:
				package.append("components", {
					"salary_component": row.salary_component,
					"treatment": row.treatment,
					"amount_basis": row.amount_basis,
					"monthly_amount": row.monthly_amount,
					"annual_amount": row.annual_amount,
				})
			package.insert()
			package.submit()
			for row in rows:
				row.salary_package = package.name
		self.generated_packages = len(by_employee)

	def on_cancel(self):
		packages = {row.salary_package for row in self.components if row.salary_package}
		blocked = frappe.db.get_value(
			"Salary Slip",
			{"elemental_salary_package": ["in", list(packages)], "docstatus": ["!=", 2]},
			["name", "elemental_salary_package"],
			as_dict=True,
		) if packages else None
		if blocked:
			frappe.throw(
				f"Cannot cancel this revision because Salary Slip {blocked.name} uses "
				f"package {blocked.elemental_salary_package}."
			)
		for name in packages:
			package = frappe.get_doc("Employee Salary Package", name)
			if package.docstatus == 1:
				package.cancel()
