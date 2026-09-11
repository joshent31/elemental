"""One non-carry-forward Saturday Off allocation per Staff employee and month."""

import calendar

import frappe
from frappe.utils import getdate, nowdate


LEAVE_TYPE = "Saturday Off"


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


def ensure_monthly_saturday_off_allocations(reference_date=None):
	"""Create exactly one month-bound allocation for every eligible Staff employee.

	An overlapping legacy allocation is automatically replaced only when it has no
	approved/submitted leave usage. Used allocations are preserved and logged for HR
	review so historical leave is never silently changed.
	"""
	if not frappe.db.exists("Leave Type", LEAVE_TYPE):
		return {"created": 0, "existing": 0, "needs_review": 0}

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
