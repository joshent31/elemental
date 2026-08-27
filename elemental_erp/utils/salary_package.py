import frappe
from frappe.utils import flt, getdate

from elemental_erp.elemental_erp.doctype.employee_salary_package.employee_salary_package import get_effective_package


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
	# Salary Slip.validate() only loads the assigned Salary Structure when both
	# component tables are empty. Load it first, then overlay the approved
	# employee-specific amounts; otherwise adding our first row would cause the
	# standard structure load to be skipped on manually-created slips.
	if not (doc.get("earnings") or doc.get("deductions")) and hasattr(doc, "get_emp_and_working_day_details"):
		doc.get_emp_and_working_day_details()

	package_name = get_effective_package(doc.employee, doc.end_date or doc.start_date)
	if not package_name:
		frappe.throw(
			f"No submitted Employee Salary Package is effective for {doc.employee} on "
			f"{getdate(doc.end_date or doc.start_date)}. Create/submit the package before payroll."
		)
	package = frappe.get_doc("Employee Salary Package", package_name)
	doc.elemental_salary_package = package.name

	for treatment, table_field in (("Earning", "earnings"), ("Deduction", "deductions")):
		for component in (row for row in package.components if row.treatment == treatment):
			_set_component_amount(doc, table_field, component.salary_component, component.monthly_amount)

	_apply_worker_ot(doc)


def _set_component_amount(doc, table_field, component_name, amount):
	rows = doc.get(table_field) or []
	row = next((item for item in rows if item.salary_component == component_name), None)
	if not row:
		row = doc.append(table_field, {"salary_component": component_name})
	defaults = frappe.db.get_value(
		"Salary Component",
		component_name,
		["salary_component_abbr", "depends_on_payment_days", "do_not_include_in_total", "statistical_component"],
		as_dict=True,
	) or frappe._dict()
	row.abbr = defaults.salary_component_abbr
	row.depends_on_payment_days = defaults.depends_on_payment_days
	row.do_not_include_in_total = defaults.do_not_include_in_total
	row.statistical_component = defaults.statistical_component
	row.amount_based_on_formula = 0
	row.formula = None
	row.default_amount = flt(amount, 6)
	row.amount = flt(amount, 6)


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
