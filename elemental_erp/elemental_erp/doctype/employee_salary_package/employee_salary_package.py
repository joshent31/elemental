import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


PACKAGE_TREATMENTS = ("Earning", "Deduction", "Employer Contribution")


class EmployeeSalaryPackage(Document):
	def validate(self):
		self._validate_employee()
		self._validate_components()
		self._calculate_totals()

	def before_submit(self):
		if frappe.db.exists(
			"Employee Salary Package",
			{"employee": self.employee, "effective_from": self.effective_from, "docstatus": 1, "name": ["!=", self.name]},
		):
			frappe.throw(f"A submitted salary package already exists for {self.employee} from {self.effective_from}.")

	def on_submit(self):
		frappe.db.set_value("Employee", self.employee, "use_elemental_salary_package", 1, update_modified=False)

	def before_cancel(self):
		slip = frappe.db.get_value("Salary Slip", {"elemental_salary_package": self.name, "docstatus": ["!=", 2]}, "name")
		if slip:
			frappe.throw(f"Cannot cancel this package because Salary Slip {slip} uses it. Cancel or delete that slip first.")

	def on_cancel(self):
		other = frappe.db.exists("Employee Salary Package", {"employee": self.employee, "docstatus": 1, "name": ["!=", self.name]})
		if not other:
			frappe.db.set_value("Employee", self.employee, "use_elemental_salary_package", 0, update_modified=False)

	def _validate_employee(self):
		employee = frappe.db.get_value("Employee", self.employee, ["status", "company", "date_of_joining"], as_dict=True)
		if not employee:
			frappe.throw(f"Employee {self.employee} does not exist.")
		if employee.status != "Active":
			frappe.throw(f"Salary Package can only be submitted for an active employee: {self.employee}.")
		if employee.date_of_joining and getdate(self.effective_from) < getdate(employee.date_of_joining):
			frappe.throw(
				f"Effective From cannot be before {self.employee}'s Date of Joining ({employee.date_of_joining})."
			)
		self.company = employee.company

	def _validate_components(self):
		if not self.components:
			frappe.throw("Add at least one salary component.")
		seen = set()
		for row in self.components:
			row.employee = None
			row.salary_package = None
			key = (row.salary_component, row.treatment)
			if key in seen:
				frappe.throw(f"Component {row.salary_component} is repeated under {row.treatment}.")
			seen.add(key)
			if row.treatment not in PACKAGE_TREATMENTS:
				frappe.throw(f"Select a valid treatment for {row.salary_component}.")
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
				frappe.throw(f"Amounts cannot be negative for {row.salary_component}.")

	def _calculate_totals(self):
		monthly = {treatment: 0 for treatment in PACKAGE_TREATMENTS}
		annual_ctc = 0
		for row in self.components:
			monthly[row.treatment] += flt(row.monthly_amount)
			if row.treatment in ("Earning", "Employer Contribution"):
				annual_ctc += flt(row.annual_amount)
		self.monthly_earnings = flt(monthly["Earning"], 2)
		self.monthly_deductions = flt(monthly["Deduction"], 2)
		self.monthly_take_home = flt(self.monthly_earnings - self.monthly_deductions, 2)
		self.monthly_employer_contribution = flt(monthly["Employer Contribution"], 2)
		self.monthly_ctc = flt(self.monthly_earnings + self.monthly_employer_contribution, 2)
		self.annual_ctc = flt(annual_ctc, 2)


def get_effective_package(employee, payroll_date):
	return frappe.db.get_value(
		"Employee Salary Package",
		{"employee": employee, "effective_from": ["<=", getdate(payroll_date)], "docstatus": 1},
		"name",
		order_by="effective_from desc, creation desc",
	)
