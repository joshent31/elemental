import frappe
from frappe.utils import now_datetime, nowdate, time_diff_in_hours

from elemental_erp.utils.qr_generator import generate_qr_image


def generate_employee_qr(doc, method=None):
	"""hooked on Employee.after_insert. Every Employee gets a unique QR the
	moment they're created \u2014 print it onto their ID badge. Scanning it at
	/gate-scan is what drives check-in/out (see gate_scan() in api.py)."""
	if doc.get("employee_qr_value"):
		return  # already has one (e.g. re-triggered by a data import)

	qr_value = frappe.generate_hash(length=12).upper()
	scan_url = frappe.utils.get_url(f"/gate-scan?qr={qr_value}")
	file_url = generate_qr_image(qr_value, scan_url, "Employee", doc.name)

	frappe.db.set_value(
		"Employee", doc.name,
		{"employee_qr_value": qr_value, "employee_qr_image": file_url},
	)


def upsert_attendance_for_day(employee, date):
	"""Rebuilds today's Attendance from today's Employee Checkins \u2014 first
	IN to last OUT for a simple total-hours figure (this does not net out
	unpaid breaks in the middle of the day; see README for that caveat).
	Creates the Attendance if it doesn't exist yet, or updates it if it
	does. Attempts to submit it; if that fails (holiday, approved leave,
	an existing conflicting record, etc.) it's left as a Draft for HR to
	sort out by hand rather than blocking the gate scan itself."""
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]]},
		fields=["log_type", "time"],
		order_by="time asc",
	)
	if not checkins:
		return None

	in_times = [row.time for row in checkins if row.log_type == "IN"]
	out_times = [row.time for row in checkins if row.log_type == "OUT"]
	if not in_times:
		return None

	first_in = min(in_times)
	last_out = max(out_times) if out_times else None
	working_hours = round(time_diff_in_hours(last_out, first_in), 2) if last_out else 0

	status = "Present"
	if working_hours and working_hours < 4:
		status = "Half Day"

	company = frappe.db.get_value("Employee", employee, "company")
	existing = frappe.db.get_value("Attendance", {"employee": employee, "attendance_date": date}, "name")

	values = {
		"employee": employee,
		"attendance_date": date,
		"company": company,
		"status": status,
		"in_time": first_in,
		"out_time": last_out,
		"working_hours": working_hours,
	}

	if existing:
		att = frappe.get_doc("Attendance", existing)
		if att.docstatus == 1:
			att.cancel()
			att = frappe.get_doc({"doctype": "Attendance", **values})
		else:
			att.update(values)
	else:
		att = frappe.get_doc({"doctype": "Attendance", **values})

	if att.is_new():
		att.insert(ignore_permissions=True)
	else:
		att.save(ignore_permissions=True)

	try:
		att.submit()
	except Exception:
		# leave it saved-but-unsubmitted rather than blocking the gate scan;
		# HR can review and submit it manually (e.g. leave conflicts, holidays)
		frappe.log_error(
			title=f"Auto-attendance: could not submit for {employee} on {date}",
			message=frappe.get_traceback(),
		)

	return att.name
