import frappe
from frappe.utils import get_datetime, getdate, now_datetime, nowdate, time_diff_in_hours

from elemental_erp.utils.qr_generator import generate_qr_image


def process_attendance_after_checkin(checkin):
	"""Gate scans only create Checkins; the selected engine processes Attendance."""
	if frappe.db.get_single_value("Elemental Attendance Settings", "enable_elemental_day_end_attendance"):
		return None, "Elemental Day-End Attendance"
	return None, "Standard HRMS / Manual Attendance"


def _is_non_working_day(employee, attendance_date):
	if getdate(attendance_date).weekday() == 6:  # Sunday is the organisation-wide week off.
		return True
	holiday_list, company = frappe.db.get_value("Employee", employee, ["holiday_list", "company"])
	holiday_list = holiday_list or frappe.db.get_value("Company", company, "default_holiday_list")
	return bool(holiday_list and frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": attendance_date}))


def _has_approved_leave(employee, attendance_date):
	return bool(frappe.db.exists("Leave Application", {
		"employee": employee, "docstatus": 1, "status": "Approved",
		"from_date": ["<=", attendance_date], "to_date": [">=", attendance_date],
	}))


def _has_approved_wfh(employee, attendance_date):
	return bool(frappe.db.exists("Work from Home Request", {
		"employee": employee, "status": "Approved",
		"from_date": ["<=", attendance_date], "to_date": [">=", attendance_date],
	}))


def build_day_end_attendance(employee, attendance_date, settings=None):
	"""Create one Present/Absent record from the first IN and final later OUT."""
	settings = settings or frappe.get_single("Elemental Attendance Settings")
	if _is_non_working_day(employee, attendance_date) or _has_approved_leave(employee, attendance_date):
		return "Skipped", None
	existing = frappe.db.get_value("Attendance", {
		"employee": employee, "attendance_date": attendance_date, "docstatus": ["<", 2]
	}, "name")
	if existing:
		return "Existing", existing
	is_wfh = _has_approved_wfh(employee, attendance_date)
	checkins = frappe.get_all("Employee Checkin", {
		"employee": employee,
		"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
	}, ["log_type", "time"], order_by="time asc", limit_page_length=0)
	in_times = [get_datetime(row.time) for row in checkins if row.log_type == "IN"]
	out_times = [get_datetime(row.time) for row in checkins if row.log_type == "OUT"]
	first_in = min(in_times) if in_times else None
	valid_outs = [value for value in out_times if first_in and value > first_in]
	last_out = max(valid_outs) if valid_outs else None
	present = is_wfh or bool(first_in and (last_out or not settings.require_out_scan))
	working_hours = round(time_diff_in_hours(last_out, first_in), 2) if first_in and last_out else 0
	company = frappe.db.get_value("Employee", employee, "company")
	doc = frappe.get_doc({
		"doctype":"Attendance", "employee":employee, "attendance_date":attendance_date,
		"company":company, "status":"Present" if present else "Absent",
		"in_time":first_in, "out_time":last_out, "working_hours":working_hours,
	})
	if is_wfh:
		doc.work_from_home = 1
	doc.insert(ignore_permissions=True)
	if settings.auto_submit_attendance:
		doc.submit()
	return doc.status, doc.name


@frappe.whitelist()
def run_day_end_attendance(attendance_date=None, force=False):
	settings = frappe.get_single("Elemental Attendance Settings")
	if not settings.enable_elemental_day_end_attendance:
		return {"enabled":False, "message":"Elemental Day-End Attendance is disabled; standard HRMS/manual flow is unchanged."}
	attendance_date = getdate(attendance_date or nowdate())
	if settings.last_processed_date == attendance_date and not frappe.utils.cint(force):
		return {"enabled":True, "already_processed":True, "date":attendance_date}
	counts = {"Present":0, "Absent":0, "Existing":0, "Skipped":0, "Errors":0}
	employees = frappe.get_all("Employee", {
		"status":"Active", "date_of_joining":["<=", attendance_date],
	}, ["name", "relieving_date"], limit_page_length=0)
	for employee in employees:
		if employee.relieving_date and getdate(employee.relieving_date) < attendance_date:
			continue
		try:
			result, _name = build_day_end_attendance(employee.name, attendance_date, settings)
			counts[result] = counts.get(result, 0) + 1
		except Exception:
			counts["Errors"] += 1
			frappe.log_error(frappe.get_traceback(), f"Day-end attendance: {employee.name} / {attendance_date}")
	summary = ", ".join(f"{key}: {value}" for key, value in counts.items())
	frappe.db.set_single_value("Elemental Attendance Settings", "last_processed_date", attendance_date)
	frappe.db.set_single_value("Elemental Attendance Settings", "last_run_summary", summary)
	return {"enabled":True, "date":attendance_date, "counts":counts, "summary":summary}


def scheduled_day_end_attendance():
	settings = frappe.get_single("Elemental Attendance Settings")
	if not settings.enable_elemental_day_end_attendance:
		return
	if now_datetime().hour >= int(settings.day_end_hour or 23):
		run_day_end_attendance()


def clear_copied_employee_qr(doc, method=None):
	"""A duplicated Employee inherits custom QR fields from its source record.
	Clear them before insertion so the new employee cannot reuse another
	employee's gate identity and after_insert can generate a fresh QR."""
	doc.employee_qr_value = None
	doc.employee_qr_image = None


def generate_employee_qr(doc, method=None):
	"""hooked on Employee.after_insert. Every Employee gets a unique QR the
	moment they're created \u2014 print it onto their ID badge. Scanning it at
	/elemental-gate-scan is what drives check-in/out (see gate_scan() in api.py)."""
	if doc.get("employee_qr_value"):
		return  # already has one (e.g. re-triggered by a data import)

	qr_value = frappe.generate_hash(length=12).upper()
	scan_url = frappe.utils.get_url(f"/elemental-gate-scan?qr={qr_value}")
	file_url = generate_qr_image(
		qr_value,
		scan_url,
		"Employee",
		doc.name,
		label=f"Employee ID: {doc.name}",
	)

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
