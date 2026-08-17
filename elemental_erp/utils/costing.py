import frappe


def hourly_rate(employee=None):
	"""Rough hourly rate for manpower costing: Employee.ctc / 208 (a ~40hr/wk,
	4.33wk/month approximation). Returns 0 if no Employee is linked or no
	ctc is set - callers should treat 0-cost lines as "not yet costed"
	rather than "free"."""
	if not employee:
		return 0
	ctc = frappe.db.get_value("Employee", employee, "ctc")
	return (ctc or 0) / 208


def compute_cost(employee, hours):
	return hourly_rate(employee) * (hours or 0)
