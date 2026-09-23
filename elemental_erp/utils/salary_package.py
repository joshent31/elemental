import frappe
from frappe.utils import flt, getdate

from elemental_erp.elemental_erp.doctype.employee_salary_package.employee_salary_package import get_effective_package

STATUTORY_ABBRS = {"PF", "EPF", "ESI", "ESIC", "PT"}
ELEMENTAL_STRUCTURE_PREFIX = "Elemental Salary Package"


def apply_employee_salary_package(doc, method=None):
	"""Supply approved fixed amounts before ERPNext performs its normal validation.

	ERPNext remains responsible for payment days, taxes, gross/net calculations,
	Payroll Entry, accounting and submission. Employees are opted in only after
	their first Employee Salary Package is submitted, so existing payroll remains
	unchanged during rollout.
	"""
	if doc.docstatus != 0 or not doc.employee or not doc.start_date:
		return
	if not frappe.db.get_value("Employee", doc.employee, "use_elemental_salary_package"):
		return
	package_name = get_effective_package(doc.employee, doc.end_date or doc.start_date)
	if not package_name:
		frappe.throw(
			f"No submitted Employee Salary Package is effective for {doc.employee} on "
			f"{getdate(doc.end_date or doc.start_date)}. Create/submit the package before payroll."
		)
	package = frappe.get_doc("Employee Salary Package", package_name)
	doc.elemental_salary_package = package.name
	ensure_salary_structure_assignment(package)

	# Salary Slip.validate() loads attendance, leave and payment-day details from
	# the assigned Salary Structure. The assignment is auto-created for package
	# employees, so Payroll Entry and manual slips can use the standard flow.
	if not (doc.get("earnings") or doc.get("deductions")) and hasattr(doc, "get_emp_and_working_day_details"):
		doc.get_emp_and_working_day_details()

	for treatment, table_field in (("Earning", "earnings"), ("Deduction", "deductions")):
		for component in (
			row for row in package.components
			if row.treatment == treatment and not _is_statutory(row.salary_component)
		):
			_set_component_amount(doc, table_field, component.salary_component, component.monthly_amount)

	_apply_worker_ot(doc)
	_apply_statutory_deductions(doc, package)


def _component_defaults(component_name):
	return frappe.db.get_value(
		"Salary Component",
		component_name,
		["salary_component_abbr", "depends_on_payment_days", "do_not_include_in_total", "statistical_component"],
		as_dict=True,
	) or frappe._dict()


def _is_statutory(component_name):
	return (_component_defaults(component_name).salary_component_abbr or "").strip().upper() in STATUTORY_ABBRS


def _set_component_amount(doc, table_field, component_name, amount, depends_on_payment_days=None):
	rows = doc.get(table_field) or []
	row = next((item for item in rows if item.salary_component == component_name), None)
	if not row:
		row = doc.append(table_field, {"salary_component": component_name})
	defaults = _component_defaults(component_name)
	row.abbr = defaults.salary_component_abbr
	row.depends_on_payment_days = defaults.depends_on_payment_days if depends_on_payment_days is None else int(depends_on_payment_days)
	row.do_not_include_in_total = defaults.do_not_include_in_total
	row.statistical_component = defaults.statistical_component
	row.amount_based_on_formula = 0
	row.formula = None
	row.default_amount = flt(amount, 6)
	row.amount = flt(amount, 6)


def _payment_day_ratio(doc):
	total = flt(doc.get("total_working_days"))
	paid = flt(doc.get("payment_days"))
	if total <= 0:
		return 1
	return max(0, min(paid / total, 1))


def _payable_package_earnings(doc, package):
	"""Return payable earning amounts after the Salary Slip payment-day ratio."""
	ratio = _payment_day_ratio(doc)
	amounts = {}
	for row in package.components:
		if row.treatment != "Earning" or _is_statutory(row.salary_component):
			continue
		defaults = _component_defaults(row.salary_component)
		amount = flt(row.monthly_amount)
		if defaults.depends_on_payment_days:
			amount *= ratio
		component_name = (row.salary_component or "").strip().lower()
		if component_name == "basic":
			key = "BASIC"
		elif component_name in ("da", "dearness allowance"):
			key = "DA"
		else:
			key = (defaults.salary_component_abbr or row.salary_component).strip().upper()
		amounts[key] = flt(amount, 6)
	if flt(doc.get("overtime_amount")):
		amounts["OT"] = flt(doc.overtime_amount, 6)
	return amounts


def calculate_statutory_amounts(payable_earnings, month):
	"""Calculate employee PF, ESIC and Karnataka Professional Tax."""
	pf_wages = flt(payable_earnings.get("BASIC")) + flt(payable_earnings.get("DA"))
	payable_gross = sum(flt(value) for value in payable_earnings.values())
	return {
		"PF": flt(min(pf_wages, 15000) * 0.12, 2),
		"ESIC": flt(payable_gross * 0.0075, 2),
		"PT": (300 if int(month) == 2 else 200) if payable_gross >= 25000 else 0,
		"payable_gross": flt(payable_gross, 2),
	}


def _apply_statutory_deductions(doc, package):
	amounts = calculate_statutory_amounts(
		_payable_package_earnings(doc, package),
		getdate(doc.end_date or doc.start_date).month,
	)
	for component in (row for row in package.components if row.treatment == "Deduction"):
		abbr = (_component_defaults(component.salary_component).salary_component_abbr or "").strip().upper()
		if abbr not in STATUTORY_ABBRS:
			continue
		amount = 0
		if abbr in ("PF", "EPF"):
			amount = amounts["PF"]
		elif abbr in ("ESI", "ESIC"):
			amount = amounts["ESIC"]
		elif abbr == "PT":
			amount = amounts["PT"]
		_set_component_amount(doc, "deductions", component.salary_component, amount, depends_on_payment_days=False)


def _apply_worker_ot(doc):
	if not frappe.db.get_value("Employee", doc.employee, "employee_category") == "Worker":
		return
	from elemental_erp.api import calculate_slip_ot

	ot = calculate_slip_ot(doc.employee, doc.start_date, doc.end_date)
	if not ot:
		return
	doc.overtime_hours = ot["ot_hours"]
	doc.overtime_rate = ot["hourly_rate"]
	doc.overtime_amount = ot["ot_amount"]
	# The Overtime component may already be part of the assigned Salary
	# Structure. Ensure it exists so bulk Payroll Entry works without the
	# manual form button.
	_set_component_amount(doc, "earnings", "Overtime", ot["ot_amount"])


def ensure_salary_structure_assignment(package):
	"""Create the ERPNext assignment needed for Payroll Entry compatibility."""
	if isinstance(package, str):
		package = frappe.get_doc("Employee Salary Package", package)
	if not package.employee or not package.effective_from:
		return
	if not frappe.db.get_value("Employee", package.employee, "use_elemental_salary_package"):
		frappe.db.set_value("Employee", package.employee, "use_elemental_salary_package", 1, update_modified=False)

	existing = frappe.db.get_value(
		"Salary Structure Assignment",
		{
			"employee": package.employee,
			"from_date": ["<=", getdate(package.effective_from)],
			"docstatus": 1,
		},
		"name",
		order_by="from_date desc, creation desc",
	)
	if existing:
		return existing

	company = package.company or frappe.db.get_value("Employee", package.employee, "company")
	currency = package.currency or frappe.db.get_value("Company", company, "default_currency") or "INR"
	structure = _ensure_elemental_salary_structure(company, currency)
	assignment = frappe.new_doc("Salary Structure Assignment")
	assignment.employee = package.employee
	assignment.company = company
	assignment.salary_structure = structure
	assignment.from_date = getdate(package.effective_from)
	assignment.currency = currency
	assignment.base = flt(package.monthly_earnings)
	assignment.insert(ignore_permissions=True, ignore_mandatory=True)
	assignment.submit()
	return assignment.name


def _ensure_elemental_salary_structure(company, currency):
	name = f"{ELEMENTAL_STRUCTURE_PREFIX} - {company}"
	if frappe.db.exists("Salary Structure", name):
		return name

	structure = frappe.new_doc("Salary Structure")
	structure.salary_structure_name = name
	structure.company = company
	structure.currency = currency
	structure.payroll_frequency = "Monthly"
	structure.is_active = "Yes"
	earning = frappe.db.exists("Salary Component", "Basic") or frappe.db.get_value(
		"Salary Component", {"type": "Earning", "disabled": 0}, "name", order_by="name asc"
	)
	if earning:
		structure.append("earnings", {"salary_component": earning, "amount": 0})
	structure.insert(ignore_permissions=True, ignore_mandatory=True)
	if getattr(structure, "docstatus", 0) == 0 and hasattr(structure, "submit"):
		structure.submit()
	return structure.name


def backfill_salary_structure_assignments():
	"""Ensure old submitted packages can run Payroll Entry after deployment."""
	if not frappe.db.exists("DocType", "Employee Salary Package"):
		return
	for package in frappe.get_all(
		"Employee Salary Package",
		filters={"docstatus": 1},
		fields=["name"],
		limit_page_length=0,
	):
		try:
			ensure_salary_structure_assignment(package.name)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Elemental salary structure assignment failed for {package.name}",
			)
