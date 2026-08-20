"""Worker Attendance Report — Script Report.

Matches the PayRepWorkersAttn Excel format:
- Employee info (S.No, Location, Code, Name, Department, Designation)
- Monthly summary (Month days, Paid, QR, PH, LOP)
- Pay structure (Monthly salary, Hourly rate, Attendance salary)
- OT summary (Total OT hours/amount, Payslip OT hours/amount, Balance payable)
- Daily columns (IN, OUT, OT Hrs, OT Amt, Job, Brand) for each day of the month
"""
import calendar
import frappe
from frappe.utils import getdate, format_duration


def execute(filters=None):
	filters = filters or {}
	year = filters.get("year") or getdate().year
	month = filters.get("month") or getdate().month
	department = filters.get("department")

	from elemental_erp.utils.worker_overtime import get_worker_attendance_report_data

	data = get_worker_attendance_report_data(year, month, department)
	columns = get_columns(year, month)
	summary = get_summary(data)

	# Flatten daily data into each row
	for i, row in enumerate(data):
		row["sno"] = i + 1
		days_in_month = row.get("days_in_month", 31)
		for day_info in row.get("daily_data", []):
			day = getdate(day_info["date"]).day
			prefix = f"d{day}"
			status = day_info.get("status", "")
			if status in ("A", "L", "PH", "W/O"):
				row[f"{prefix}_in"] = status
			else:
				row[f"{prefix}_in"] = format_time(day_info.get("in_time"))
				row[f"{prefix}_out"] = format_time(day_info.get("out_time"))
				ot_hrs = day_info.get("ot_hours", 0)
				if ot_hrs > 0:
					h = int(ot_hrs)
					m = int(round((ot_hrs - h) * 60))
					row[f"{prefix}_ot"] = f"{h}:{m:02d}"
					row[f"{prefix}_amt"] = day_info.get("ot_amount", 0)
				row[f"{prefix}_job"] = day_info.get("job", "")
				row[f"{prefix}_brand"] = day_info.get("brand", "")

	return columns, data, None, summary


def get_columns(year, month):
	"""Build columns matching the Excel format."""
	days_in_month = calendar.monthrange(year, month)[1]

	columns = [
		{"label": "S.No", "fieldname": "sno", "fieldtype": "Int", "width": 45},
		{"label": "Location", "fieldname": "location", "fieldtype": "Data", "width": 120},
		{"label": "Code", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 70},
		{"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": "Dept", "fieldname": "department", "fieldtype": "Data", "width": 100},
		{"label": "Designation", "fieldname": "designation", "fieldtype": "Data", "width": 120},
		# Monthly summary
		{"label": "Month", "fieldname": "days_in_month", "fieldtype": "Int", "width": 50},
		{"label": "Paid", "fieldname": "paid_days", "fieldtype": "Float", "width": 50, "precision": "1"},
		{"label": "QR", "fieldname": "qr_days", "fieldtype": "Int", "width": 40},
		{"label": "PH", "fieldname": "ph_days", "fieldtype": "Int", "width": 40},
		{"label": "LOP", "fieldname": "lop_days", "fieldtype": "Float", "width": 45, "precision": "1"},
		# Pay structure
		{"label": "/Month", "fieldname": "monthly_salary", "fieldtype": "Currency", "width": 90},
		{"label": "/Hour", "fieldname": "hourly_rate", "fieldtype": "Float", "width": 80, "precision": "2"},
		{"label": "Att.Salary", "fieldname": "att_salary", "fieldtype": "Currency", "width": 100},
		# Total OT
		{"label": "OT Hours", "fieldname": "total_ot_hours_fmt", "fieldtype": "Data", "width": 80},
		{"label": "OT Amount", "fieldname": "total_ot_amount", "fieldtype": "Currency", "width": 100},
		# Payslip OT (capped at 15 hrs, shown at 2× rate)
		{"label": "Payslip OT Hrs", "fieldname": "salary_slip_ot_hours_fmt", "fieldtype": "Data", "width": 100},
		{"label": "Payslip OT Amt", "fieldname": "salary_slip_ot_amount", "fieldtype": "Currency", "width": 110},
		# Cash OT (remaining 3 hrs at 2× rate)
		{"label": "Cash OT Hrs", "fieldname": "cash_ot_hours_fmt", "fieldtype": "Data", "width": 90},
		{"label": "Cash OT Amt", "fieldname": "cash_ot_amount", "fieldtype": "Currency", "width": 100},
		# Balance
		{"label": "Balance Payable", "fieldname": "total_earnings", "fieldtype": "Currency", "width": 120},
	]

	# Daily columns for each day of the month
	for day in range(1, days_in_month + 1):
		date_str = f"{year}-{month:02d}-{day:02d}"
		prefix = f"d{day}"

		columns.append({"label": f"{day} IN", "fieldname": f"{prefix}_in", "fieldtype": "Data", "width": 75})
		columns.append({"label": f"{day} OUT", "fieldname": f"{prefix}_out", "fieldtype": "Data", "width": 75})
		columns.append({"label": f"{day} OT", "fieldname": f"{prefix}_ot", "fieldtype": "Data", "width": 55})
		columns.append({"label": f"{day} Amt", "fieldname": f"{prefix}_amt", "fieldtype": "Currency", "width": 75})
		columns.append({"label": f"{day} Job", "fieldname": f"{prefix}_job", "fieldtype": "Data", "width": 80})
		columns.append({"label": f"{day} Brand", "fieldname": f"{prefix}_brand", "fieldtype": "Data", "width": 90})

	return columns


def get_summary(data):
	"""Summary row at the top showing totals."""
	if not data:
		return None

	total_paid = sum(d.get("paid_days", 0) for d in data)
	total_ph = sum(d.get("ph_days", 0) for d in data)
	total_lop = sum(d.get("lop_days", 0) for d in data)
	total_salary = sum(d.get("monthly_salary", 0) for d in data)
	total_att_salary = sum(d.get("att_salary", 0) for d in data)
	total_ot_hours = sum(d.get("total_ot_hours", 0) for d in data)
	total_ot_amount = sum(d.get("total_ot_amount", 0) for d in data)
	total_slip_ot = sum(d.get("salary_slip_ot_amount", 0) for d in data)
	total_cash_ot = sum(d.get("cash_ot_amount", 0) for d in data)
	total_earnings = sum(d.get("total_earnings", 0) for d in data)

	def fmt_hhmm(hours):
		h = int(hours)
		m = int(round((hours - h) * 60))
		return f"{h}:{m:02d}"

	# Return as a message dict shown above the report
	return {
		"message": (
			f"Total Workers: {len(data)} | "
			f"Paid Days: {total_paid:.0f} | PH: {total_ph} | LOP: {total_lop:.0f} | "
			f"Total Monthly: {frappe.format_currency(total_salary)} | "
		 f"Att.Salary: {frappe.format_currency(total_att_salary)} | "
		 f"Total OT: {fmt_hhmm(total_ot_hours)} ({frappe.format_currency(total_ot_amount)}) | "
		 f"Payslip OT: {frappe.format_currency(total_slip_ot)} | "
		 f"Cash OT: {frappe.format_currency(total_cash_ot)} | "
		 f"Total Earnings: {frappe.format_currency(total_earnings)}"
		)
	}


def format_time(dt):
	"""Format datetime to AM/PM string like the Excel."""
	if not dt:
		return ""
	try:
		return getdate(dt).strftime("%I:%M%p").lstrip("0")
	except Exception:
		return str(dt)
