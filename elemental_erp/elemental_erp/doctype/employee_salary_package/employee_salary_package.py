import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


PACKAGE_TREATMENTS = ("Earning", "Deduction", "Employer Contribution")
AUTOMATIC_COMPONENT_ABBRS = {"PF", "EPF", "ESI", "ESIC", "PT"}
COMPONENT_ORDER = {
	"basic": 10,
	"house rent allowance": 20,
	"hra": 20,
	"dearness allowance": 30,
	"da": 30,
	"provident fund": 1010,
	"pf": 1010,
	"epf": 1010,
	"esic": 1020,
	"esi": 1020,
	"professional tax": 1030,
	"pt": 1030,
	"income tax": 1040,
}


def _component_abbr(name):
	return (frappe.db.get_value("Salary Component", name, "salary_component_abbr") or "").strip().upper()


def _is_automatic_component(name):
	return _component_abbr(name) in AUTOMATIC_COMPONENT_ABBRS


def _component_sort_key(row):
	name = (row.salary_component or row.get("name") or "").strip().lower()
	treatment = row.treatment or row.get("type")
	group = 0 if treatment == "Earning" else 1000 if treatment == "Deduction" else 2000
	return (COMPONENT_ORDER.get(name, group + 100), name)


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
			component_type = frappe.db.get_value("Salary Component", row.salary_component, "type")
			if not component_type:
				frappe.throw(f"Salary Component {row.salary_component} does not exist.")
			row.treatment = row.treatment or component_type
			key = (row.salary_component, row.treatment)
			if key in seen:
				frappe.throw(f"Component {row.salary_component} is repeated under {row.treatment}.")
			seen.add(key)
			if row.treatment not in PACKAGE_TREATMENTS:
				frappe.throw(f"Select a valid treatment for {row.salary_component}.")
			if row.treatment != "Employer Contribution" and component_type != row.treatment:
				frappe.throw(f"{row.salary_component} is a {component_type}, not a {row.treatment}.")
			row.automatic_calculation = int(_is_automatic_component(row.salary_component))
			# Existing packages pre-date the Use checkbox. A non-zero amount keeps
			# those approved rows enabled after migration.
			if not row.enabled and (flt(row.monthly_amount) or flt(row.annual_amount)):
				row.enabled = 1
			if not row.enabled or row.automatic_calculation:
				row.monthly_amount = 0
				row.annual_amount = 0
				if not row.enabled:
					continue
			if row.amount_basis == "Annual":
				row.annual_amount = flt(row.annual_amount, 2)
				row.monthly_amount = flt(row.annual_amount / 12, 6)
			else:
				row.amount_basis = "Monthly"
				row.monthly_amount = flt(row.monthly_amount, 6)
				row.annual_amount = flt(row.monthly_amount * 12, 2)
			if row.monthly_amount < 0 or row.annual_amount < 0:
				frappe.throw(f"Amounts cannot be negative for {row.salary_component}.")
		self.components.sort(key=_component_sort_key)
		for index, row in enumerate(self.components, 1):
			row.idx = index

	def _calculate_totals(self):
		self._calculate_statutory_preview()
		monthly = {treatment: 0 for treatment in PACKAGE_TREATMENTS}
		annual_ctc = 0
		for row in self.components:
			if not row.enabled:
				continue
			monthly[row.treatment] += flt(row.monthly_amount)
			if row.treatment in ("Earning", "Employer Contribution"):
				annual_ctc += flt(row.annual_amount)
		self.monthly_earnings = flt(monthly["Earning"], 2)
		self.monthly_deductions = flt(monthly["Deduction"], 2)
		self.monthly_take_home = flt(self.monthly_earnings - self.monthly_deductions, 2)
		self.monthly_employer_contribution = flt(monthly["Employer Contribution"], 2)
		self.monthly_ctc = flt(self.monthly_earnings + self.monthly_employer_contribution, 2)
		self.annual_ctc = flt(annual_ctc, 2)

	def _calculate_statutory_preview(self):
		"""Show full-month statutory estimates; Salary Slip recalculates payable values."""
		earnings = [row for row in self.components if row.enabled and row.treatment == "Earning"]
		gross = sum(flt(row.monthly_amount) for row in earnings)
		pf_wages = 0
		for row in earnings:
			abbr = _component_abbr(row.salary_component)
			name = (row.salary_component or "").strip().lower()
			if name == "basic" or abbr == "BASIC":
				pf_wages += flt(row.monthly_amount)
			elif name in ("da", "dearness allowance") or abbr == "DA":
				pf_wages += flt(row.monthly_amount)
		for row in self.components:
			if not row.enabled or row.treatment != "Deduction" or not row.automatic_calculation:
				continue
			abbr = _component_abbr(row.salary_component)
			if abbr in ("PF", "EPF"):
				row.monthly_amount = flt(min(pf_wages, 15000) * 0.12, 2)
				row.annual_amount = flt(row.monthly_amount * 12, 2)
			elif abbr in ("ESI", "ESIC"):
				row.monthly_amount = flt(gross * 0.0075, 2)
				row.annual_amount = flt(row.monthly_amount * 12, 2)
			elif abbr == "PT":
				row.monthly_amount = 200 if gross >= 25000 else 0
				row.annual_amount = 2500 if gross >= 25000 else 0


def get_effective_package(employee, payroll_date):
	return frappe.db.get_value(
		"Employee Salary Package",
		{"employee": employee, "effective_from": ["<=", getdate(payroll_date)], "docstatus": 1},
		"name",
		order_by="effective_from desc, creation desc",
	)


@frappe.whitelist()
def get_salary_component_catalogue():
	"""Return active earning/deduction masters for the package checkbox grid."""
	rows = frappe.get_all(
		"Salary Component",
		filters={"disabled": 0},
		fields=["name", "type", "salary_component_abbr"],
		order_by="type asc, name asc",
		limit_page_length=0,
	)
	result = [
		{
			"salary_component": row.name,
			"treatment": row.type,
			"automatic_calculation": int((row.salary_component_abbr or "").strip().upper() in AUTOMATIC_COMPONENT_ABBRS),
		}
		for row in rows
		if row.type in ("Earning", "Deduction")
	]
	return sorted(result, key=_component_sort_key)
