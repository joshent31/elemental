import calendar
from collections import Counter, defaultdict

import frappe
from frappe.utils import getdate, time_diff_in_hours


TOLERANCE_HOURS = 0.25


def execute(filters=None):
	filters = frappe._dict(filters or {})
	year = int(filters.get("year") or getdate().year)
	month = int(filters.get("month") or getdate().month)
	filters.from_date = getdate(f"{year}-{month:02d}-01")
	filters.to_date = getdate(f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}")

	requests = get_requests(filters)
	checkouts = get_checkouts(filters)
	rows = build_rows(requests, checkouts, filters)
	return get_columns(), rows, "Payable OT is calculated only for HR-approved requests and is capped at the lower of requested versus actual OT.", get_chart(rows)


def get_chart(rows):
	if not rows:
		return None
	counts = Counter(row.get("reconciliation") or "Unknown" for row in rows)
	return {
		"data": {"labels": list(counts), "datasets": [{"name": "Employees", "values": list(counts.values())}]},
		"type": "donut",
		"colors": ["#2e7d32", "#c62828", "#ef6c00", "#1565c0", "#7b61ff", "#546e7a"],
	}


def get_requests(filters):
	request_filters = {"docstatus": 1, "ot_date": ["between", [filters.from_date, filters.to_date]]}
	if filters.department:
		request_filters["department"] = filters.department
	if filters.request_status:
		request_filters["status"] = filters.request_status

	result = {}
	for request in frappe.get_all(
		"Department OT Request",
		filters=request_filters,
		fields=["name", "ot_date", "department", "status", "department_reason"],
		order_by="ot_date asc, department asc",
	):
		for row in frappe.get_all(
			"Department OT Request Employee",
			filters={"parent": request.name, "parenttype": "Department OT Request"},
			fields=["employee", "employee_name", "requested_ot_hours", "reason"],
			order_by="idx asc",
		):
			if filters.employee and row.employee != filters.employee:
				continue
			if not employee_matches_category(row.employee, filters.get("employee_category")):
				continue
			result[(str(request.ot_date), row.employee)] = frappe._dict(
				request=request.name,
				request_status=request.status,
				department=request.department,
				date=request.ot_date,
				employee=row.employee,
				employee_name=row.employee_name,
				requested_ot_hours=float(row.requested_ot_hours or 0),
				reason=row.reason or request.department_reason,
			)
	return result


def get_checkouts(filters):
	checkin_filters = {"time": ["between", [f"{filters.from_date} 00:00:00", f"{filters.to_date} 23:59:59"]]}
	if filters.employee:
		checkin_filters["employee"] = filters.employee
	checkins = frappe.get_all(
		"Employee Checkin", filters=checkin_filters, fields=["employee", "employee_name", "log_type", "time"], order_by="time asc"
	)
	by_day = defaultdict(list)
	for checkin in checkins:
		by_day[(str(getdate(checkin.time)), checkin.employee)].append(checkin)

	employee_fields = ["name", "employee_name", "department", "holiday_list"]
	if frappe.db.has_column("Employee", "employee_category"):
		employee_fields.append("employee_category")
	if frappe.get_meta("Employee").has_field("standard_shift_hours"):
		employee_fields.append("standard_shift_hours")
	employees = {
		row.name: row
		for row in frappe.get_all("Employee", filters={"name": ["in", list({key[1] for key in by_day})]}, fields=employee_fields)
	} if by_day else {}

	result = {}
	for key, entries in by_day.items():
		employee = employees.get(key[1])
		if not employee or (filters.department and employee.department != filters.department):
			continue
		if filters.get("employee_category") and employee.get("employee_category") != filters.employee_category:
			continue
		first_in = min((row.time for row in entries if row.log_type == "IN"), default=None)
		last_out = max((row.time for row in entries if row.log_type == "OUT"), default=None)
		total_hours = round(max(time_diff_in_hours(last_out, first_in), 0), 2) if first_in and last_out else 0
		shift_hours = float(employee.get("standard_shift_hours") or 8)
		work_date = getdate(key[0])
		is_holiday = bool(employee.holiday_list and frappe.db.exists("Holiday", {"parent": employee.holiday_list, "holiday_date": work_date}))
		# Saturday is worked normally. Only Sunday (weekday 6) or an explicit
		# Holiday List date treats all worked hours as OT.
		actual_ot = total_hours if work_date.weekday() == 6 or is_holiday else max(total_hours - shift_hours, 0)
		result[key] = frappe._dict(
			date=work_date, employee=employee.name, employee_name=employee.employee_name,
			department=employee.department, first_in=first_in, last_out=last_out,
			total_hours=total_hours, shift_hours=shift_hours, actual_ot_hours=round(actual_ot, 2),
		)
	return result


def employee_matches_category(employee, employee_category):
	if not employee_category or not frappe.db.has_column("Employee", "employee_category"):
		return True
	return frappe.db.get_value("Employee", employee, "employee_category") == employee_category


def build_rows(requests, checkouts, filters):
	rows = []
	for key in sorted(set(requests) | set(checkouts)):
		request = requests.get(key, frappe._dict())
		checkout = checkouts.get(key, frappe._dict())
		requested = float(request.get("requested_ot_hours") or 0)
		actual = float(checkout.get("actual_ot_hours") or 0)
		status = reconciliation_status(request.get("request_status"), requested, actual, bool(checkout.get("last_out")))
		if filters.exceptions_only and status == "Matched":
			continue
		if not request and actual <= 0:
			continue
		rows.append({
			"request": request.get("request"), "request_status": request.get("request_status") or "Not Requested",
			"department": request.get("department") or checkout.get("department"), "date": request.get("date") or checkout.get("date"),
			"employee": request.get("employee") or checkout.get("employee"), "employee_name": request.get("employee_name") or checkout.get("employee_name"),
			"first_in": checkout.get("first_in"), "last_out": checkout.get("last_out"), "total_hours": checkout.get("total_hours") or 0,
			"shift_hours": checkout.get("shift_hours") or 8, "requested_ot_hours": requested, "actual_ot_hours": actual,
			"variance_hours": round(actual - requested, 2), "payable_ot_hours": payable_ot_hours(request.get("request_status"), requested, actual),
			"reconciliation": status, "reason": request.get("reason"),
		})
	return rows


def payable_ot_hours(request_status, requested, actual):
	return round(min(requested, actual), 2) if request_status == "Approved" else 0


def reconciliation_status(request_status, requested, actual, has_checkout=True):
	if not request_status:
		return "Unauthorized OT" if actual > 0 else "No OT"
	if not has_checkout:
		return "No Checkout"
	if request_status == "Rejected" and actual > 0:
		return "Rejected OT Worked"
	if request_status == "Sent to HR":
		return "HR Approval Pending"
	if actual <= 0:
		return "No Actual OT"
	if actual > requested + TOLERANCE_HOURS:
		return "Excess OT"
	if actual < requested - TOLERANCE_HOURS:
		return "Below Request"
	return "Matched"


def get_columns():
	return [
		{"label":"OT Request","fieldname":"request","fieldtype":"Link","options":"Department OT Request","width":135},
		{"label":"Approval","fieldname":"request_status","fieldtype":"Data","width":105},
		{"label":"Department","fieldname":"department","fieldtype":"Link","options":"Department","width":130},
		{"label":"Date","fieldname":"date","fieldtype":"Date","width":95},
		{"label":"Employee","fieldname":"employee","fieldtype":"Link","options":"Employee","width":110},
		{"label":"Employee Name","fieldname":"employee_name","fieldtype":"Data","width":155},
		{"label":"First IN","fieldname":"first_in","fieldtype":"Datetime","width":145},
		{"label":"Last OUT","fieldname":"last_out","fieldtype":"Datetime","width":145},
		{"label":"Total Hrs","fieldname":"total_hours","fieldtype":"Float","precision":2,"width":80},
		{"label":"Shift Hrs","fieldname":"shift_hours","fieldtype":"Float","precision":2,"width":80},
		{"label":"Requested OT","fieldname":"requested_ot_hours","fieldtype":"Float","precision":2,"width":100},
		{"label":"Actual OT","fieldname":"actual_ot_hours","fieldtype":"Float","precision":2,"width":90},
		{"label":"Variance","fieldname":"variance_hours","fieldtype":"Float","precision":2,"width":80},
		{"label":"Payable OT","fieldname":"payable_ot_hours","fieldtype":"Float","precision":2,"width":95},
		{"label":"Reconciliation","fieldname":"reconciliation","fieldtype":"Data","width":150},
		{"label":"Reason","fieldname":"reason","fieldtype":"Small Text","width":220},
	]
