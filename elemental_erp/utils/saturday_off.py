"""One non-carry-forward Saturday Off allocation per Staff employee and month."""

import calendar

import frappe
from frappe.utils import getdate, nowdate


LEAVE_TYPE = "Saturday Off"


def is_monthly_saturday_off_enabled():
	"""Default to enabled during first migration and on older installations."""
	if not frappe.db.exists("DocType", "Elemental Attendance Settings"):
		return True
	value = frappe.db.get_single_value("Elemental Attendance Settings", "enable_monthly_saturday_off")
	return True if value is None else bool(int(value))


def _month_bounds(reference_date=None):
	date = getdate(reference_date or nowdate())
	return date.replace(day=1), date.replace(day=calendar.monthrange(date.year, date.month)[1])


def configure_saturday_off_leave():
	"""Keep the Leave Type out of HRMS earned-leave proration."""
	if not frappe.db.exists("Leave Type", LEAVE_TYPE):
		return
	frappe.db.set_value(
		"Leave Type",
		LEAVE_TYPE,
		{
			"max_leaves_allowed": 1,
			"is_earned_leave": 0,
			"is_carry_forward": 0,
			"max_continuous_days_allowed": 1,
		},
		update_modified=False,
	)


def remove_saturday_off_from_leave_policies():
	"""Remove the monthly Elemental leave from annual HRMS policies.

	Leave Policy Assignment creates an annual allocation for every policy row.
	Including Saturday Off overlaps the month-bound allocation and blocks the
	assignment. Employee allocations and applications are not deleted here.
	"""
	if not is_monthly_saturday_off_enabled():
		return 0
	rows = frappe.get_all(
		"Leave Policy Detail",
		filters={"leave_type": LEAVE_TYPE},
		fields=["name", "parent"],
		limit_page_length=0,
	)
	for row in rows:
		frappe.db.delete("Leave Policy Detail", {"name": row.name})
	if rows:
		frappe.logger("elemental_erp").info(
			"Removed Saturday Off from %s Leave Policy row(s); it is allocated monthly by Elemental.",
			len(rows),
		)
	return len(rows)


def validate_leave_policy(doc, method=None):
	"""Prevent future annual-policy overlap with monthly Saturday Off."""
	if not is_monthly_saturday_off_enabled():
		return
	if any(row.leave_type == LEAVE_TYPE for row in doc.leave_policy_details or []):
		frappe.throw(
			'Please remove "Saturday Off" from this Leave Policy. Elemental allocates '
			"one Saturday Off separately every month; adding it here creates an overlapping allocation."
		)


def ensure_monthly_saturday_off_allocations(reference_date=None):
	"""Create exactly one month-bound allocation for every eligible Staff employee.

	An overlapping legacy allocation is automatically replaced only when it has no
	approved/submitted leave usage. Used allocations are preserved and logged for HR
	review so historical leave is never silently changed.
	"""
	if not is_monthly_saturday_off_enabled() or not frappe.db.exists("Leave Type", LEAVE_TYPE):
		return {"enabled": False, "created": 0, "existing": 0, "needs_review": 0}

	month_start, month_end = _month_bounds(reference_date)
	employees = frappe.db.sql(
		"""SELECT name
		FROM `tabEmployee`
		WHERE status = 'Active'
			AND COALESCE(employee_category, '') = 'Staff'
			AND (date_of_joining IS NULL OR date_of_joining <= %(month_end)s)
			AND (relieving_date IS NULL OR relieving_date >= %(month_start)s)""",
		{"month_start": month_start, "month_end": month_end},
		as_dict=True,
	)

	result = {"created": 0, "existing": 0, "needs_review": 0}
	for employee in employees:
		overlaps = frappe.get_all(
			"Leave Allocation",
			filters={
				"employee": employee.name,
				"leave_type": LEAVE_TYPE,
				"docstatus": ["<", 2],
				"from_date": ["<=", month_end],
				"to_date": [">=", month_start],
			},
			fields=["name", "from_date", "to_date", "new_leaves_allocated", "docstatus"],
		)
		valid = next(
			(
				row
				for row in overlaps
				if getdate(row.from_date) == month_start
				and getdate(row.to_date) == month_end
				and float(row.new_leaves_allocated or 0) == 1
			),
			None,
		)
		if valid:
			result["existing"] += 1
			continue

		if overlaps and not _can_replace(employee.name, month_start, month_end):
			result["needs_review"] += 1
			frappe.log_error(
				title="Saturday Off allocation requires HR review",
				message=f"{employee.name} has a used or conflicting Saturday Off allocation for {month_start:%B %Y}.",
			)
			continue

		for row in overlaps:
			_remove_unused_allocation(row.name, row.docstatus)
		_create_monthly_allocation(employee.name, month_start, month_end)
		result["created"] += 1
	return result


def disable_monthly_saturday_off(reference_date=None):
	"""Cancel unused Elemental allocations for this month and the future.

	Used allocations are preserved for audit/history. Annual policy allocations
	are not touched because their description does not identify them as Elemental.
	"""
	month_start, _month_end = _month_bounds(reference_date)
	rows = frappe.get_all(
		"Leave Allocation",
		filters={
			"leave_type": LEAVE_TYPE,
			"docstatus": ["<", 2],
			"to_date": [">=", month_start],
			"description": ["like", "One Saturday Off for this calendar month%"],
		},
		fields=["name", "employee", "from_date", "to_date", "docstatus"],
		limit_page_length=0,
	)
	result = {"cancelled": 0, "preserved": 0}
	for row in rows:
		if _can_replace(row.employee, getdate(row.from_date), getdate(row.to_date)):
			_remove_unused_allocation(row.name, row.docstatus)
			result["cancelled"] += 1
		else:
			result["preserved"] += 1
	return result


def _can_replace(employee, month_start, month_end):
	return not frappe.db.exists(
		"Leave Application",
		{
			"employee": employee,
			"leave_type": LEAVE_TYPE,
			"docstatus": ["<", 2],
			"status": ["in", ["Open", "Approved"]],
			"from_date": ["<=", month_end],
			"to_date": [">=", month_start],
		},
	)


def _remove_unused_allocation(name, docstatus):
	doc = frappe.get_doc("Leave Allocation", name)
	doc.flags.ignore_permissions = True
	if int(docstatus or 0) == 1:
		doc.cancel()
	else:
		frappe.delete_doc("Leave Allocation", name, ignore_permissions=True, force=True)


def _create_monthly_allocation(employee, month_start, month_end):
	doc = frappe.get_doc(
		{
			"doctype": "Leave Allocation",
			"employee": employee,
			"leave_type": LEAVE_TYPE,
			"from_date": month_start,
			"to_date": month_end,
			"new_leaves_allocated": 1,
			"description": "One Saturday Off for this calendar month. Unused balance expires at month-end.",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
