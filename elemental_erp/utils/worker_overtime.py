"""Worker Overtime calculation engine.

For Worker-category employees, this module:
1. Computes daily OT hours from Employee Checkin (IN/OUT pairs)
2. Applies the government cap of 15 OT hours/month
3. Splits OT into Salary Slip portion (12 hrs × 2× rate) and Cash portion
4. Generates a summary suitable for the Worker Attendance Report

Business Rules (from client requirements):
- Standard shift = employee's standard_shift_hours (default 8)
- Any hours beyond standard shift = Overtime
- Government allows max 15 OT hours/month
- OT rate = 2× hourly rate
- Salary Slip shows: 12 OT hours × 2× hourly rate
- Cash payment: remaining (15 - 12 = 3) OT hours × 2× hourly rate
- Hours beyond 15 = not paid (for government reporting purposes)
"""
import frappe
from frappe.utils import getdate, get_datetime, time_diff_in_hours, format_duration


# Government OT cap per month
GOV_OT_CAP_HOURS = 15
# Of the 15 hrs, how many go on the salary slip
SALARY_SLIP_OT_HOURS = 12
# Cash OT = GOV_OT_CAP - SALARY_SLIP_OT
CASH_OT_HOURS = GOV_OT_CAP_HOURS - SALARY_SLIP_OT_HOURS


def hourly_rate(employee):
    """Compute hourly rate for a Worker.
    hourly_rate = monthly_salary / (days_in_month * standard_shift_hours)
    This matches the Excel report's /Hour column."""
    emp = frappe.db.get_value(
        "Employee", employee,
        ["ctc", "employee_category", "standard_shift_hours"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return 0
    shift = emp.standard_shift_hours or 8
    ctc = emp.ctc or 0
    # Use 26 working days * shift hours as denominator (standard Indian calculation)
    # But to match the Excel: Monthly / (31 * 8) = Monthly / 248
    # We'll use days_in_month * shift for accuracy
    import calendar
    today = getdate()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    denominator = days_in_month * shift
    return ctc / denominator if denominator else 0


def daily_rate(employee):
    """Daily rate = monthly_salary / days_in_month."""
    emp = frappe.db.get_value("Employee", employee, ["ctc", "employee_category"], as_dict=True)
    if not emp or emp.employee_category != "Worker":
        return 0
    import calendar
    today = getdate()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return (emp.ctc or 0) / days_in_month if days_in_month else 0


def compute_daily_ot(employee, date):
    """Compute OT hours for a single day from Employee Checkin records.
    Returns dict with in_time, out_time, total_hours, ot_hours, ot_amount."""
    emp = frappe.db.get_value(
        "Employee", employee,
        ["employee_category", "standard_shift_hours", "ctc"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return None

    shift = emp.standard_shift_hours or 8

    checkins = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]]},
        fields=["log_type", "time"],
        order_by="time asc",
    )

    if not checkins:
        return {"in_time": None, "out_time": None, "total_hours": 0, "ot_hours": 0, "ot_amount": 0, "status": "A"}

    in_times = [c.time for c in checkins if c.log_type == "IN"]
    out_times = [c.time for c in checkins if c.log_type == "OUT"]

    if not in_times:
        return {"in_time": None, "out_time": None, "total_hours": 0, "ot_hours": 0, "ot_amount": 0, "status": "A"}

    in_time = min(in_times)
    out_time = max(out_times) if out_times else None

    if not out_time:
        return {"in_time": in_time, "out_time": None, "total_hours": 0, "ot_hours": 0, "ot_amount": 0, "status": "A"}

    total_hours = round(time_diff_in_hours(out_time, in_time), 2)
    ot_hours = max(total_hours - shift, 0)
    ot_hours = round(ot_hours, 2)

    hr = hourly_rate(employee)
    ot_amount = round(ot_hours * hr, 2)

    return {
        "in_time": in_time,
        "out_time": out_time,
        "total_hours": total_hours,
        "ot_hours": ot_hours,
        "ot_amount": ot_amount,
        "status": "P",  # Present
    }


def compute_monthly_summary(employee, year, month):
    """Compute full monthly OT summary for a Worker.
    Returns dict with all fields needed for the report."""
    import calendar

    emp = frappe.db.get_value(
        "Employee", employee,
        ["employee_name", "department", "designation", "ctc",
         "employee_category", "standard_shift_hours", "company",
         "branch", "cell_number"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return None

    shift = emp.standard_shift_hours or 8
    days_in_month = calendar.monthrange(year, month)[1]
    hr = hourly_rate(employee)
    dr = daily_rate(employee)

    # Get attendance status for the month
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{days_in_month}"

    # Check for holidays
    holiday_dates = set()
    holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
    if holiday_list:
        holidays = frappe.get_all(
            "Holiday",
            filters={"parent": holiday_list, "holiday_date": ["between", [month_start, month_end]]},
            fields=["holiday_date"],
        )
        holiday_dates = {str(h.holiday_date) for h in holidays}

    # Check for leaves
    leave_dates = set()
    leaves = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "status": "Approved",
            "from_date": ["<=", month_end],
            "to_date": [">=", month_start],
        },
        fields=["from_date", "to_date"],
    )
    for leave in leaves:
        d = getdate(leave.from_date)
        while d <= getdate(leave.to_date):
            leave_dates.add(str(d))
            from frappe.utils import add_days
            d = add_days(d, 1)

    # Compute daily data
    daily_data = []
    total_ot_hours = 0
    total_ot_amount = 0
    paid_days = 0
    qr_days = 0
    ph_days = 0
    lop_days = 0

    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = getdate(date_str)

        # Check if weekend (optional — depends on company policy)
        is_weekend = date_obj.weekday() >= 5  # Saturday=5, Sunday=6

        if str(date_obj) in holiday_dates:
            daily_data.append({"date": date_str, "status": "PH", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            ph_days += 1
            continue

        if str(date_obj) in leave_dates:
            daily_data.append({"date": date_str, "status": "L", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            continue

        # Check if QR scan exists (means they checked in via gate)
        has_scan = frappe.db.exists(
            "Employee Checkin",
            {"employee": employee, "time": ["between", [f"{date_str} 00:00:00", f"{date_str} 23:59:59"]]},
        )

        if not has_scan:
            if is_weekend:
                daily_data.append({"date": date_str, "status": "W/O", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            else:
                daily_data.append({"date": date_str, "status": "A", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
                lop_days += 1
            continue

        result = compute_daily_ot(employee, date_str)
        if result["status"] == "A":
            daily_data.append({"date": date_str, "status": "A", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            lop_days += 1
            continue

        qr_days += 1
        paid_days += 1
        total_ot_hours += result["ot_hours"]
        total_ot_amount += result["ot_amount"]

        daily_data.append({
            "date": date_str,
            "status": "P",
            "in_time": result["in_time"],
            "out_time": result["out_time"],
            "total_hours": result["total_hours"],
            "ot_hours": result["ot_hours"],
            "ot_amount": result["ot_amount"],
            "job": "",
            "brand": "",
        })

    # Apply government cap
    capped_ot_hours = min(total_ot_hours, GOV_OT_CAP_HOURS)
    salary_slip_ot_hours = min(capped_ot_hours, SALARY_SLIP_OT_HOURS)
    cash_ot_hours = max(capped_ot_hours - salary_slip_ot_hours, 0)

    salary_slip_ot_amount = round(salary_slip_ot_hours * hr * 2, 2)  # 2× rate
    cash_ot_amount = round(cash_ot_hours * hr * 2, 2)  # 2× rate
    total_ot_amount_capped = round(capped_ot_hours * hr * 2, 2)

    att_salary = round(paid_days * dr, 2)
    total_earnings = round(att_salary + total_ot_amount_capped, 2)

    # Format OT hours as HH:MM
    def format_hhmm(hours):
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h}:{m:02d}"

    return {
        "employee": employee,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "designation": emp.designation,
        "location": emp.branch or "",
        "monthly_salary": emp.ctc or 0,
        "hourly_rate": round(hr, 2),
        "days_in_month": days_in_month,
        "paid_days": paid_days,
        "qr_days": qr_days,
        "ph_days": ph_days,
        "lop_days": lop_days,
        "att_salary": att_salary,
        "total_ot_hours": total_ot_hours,
        "total_ot_hours_fmt": format_hhmm(total_ot_hours),
        "total_ot_amount": round(total_ot_amount, 2),
        "salary_slip_ot_hours": salary_slip_ot_hours,
        "salary_slip_ot_hours_fmt": format_hhmm(salary_slip_ot_hours),
        "salary_slip_ot_amount": salary_slip_ot_amount,
        "cash_ot_hours": cash_ot_hours,
        "cash_ot_hours_fmt": format_hhmm(cash_ot_hours),
        "cash_ot_amount": cash_ot_amount,
        "govt_ot_hours": capped_ot_hours,
        "govt_ot_hours_fmt": format_hhmm(capped_ot_hours),
        "total_earnings": total_earnings,
        "daily_data": daily_data,
    }


def get_worker_attendance_report_data(year, month, department=None, location=None):
    """Get all Worker-category employees' attendance data for the report.
    Returns list of monthly summaries sorted by department, name."""
    filters = {"employee_category": "Worker"}
    if department:
        filters["department"] = department

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "department", "branch"],
        order_by="department asc, employee_name asc",
    )

    result = []
    for emp in employees:
        if location and emp.branch != location:
            continue
        summary = compute_monthly_summary(emp.name, year, month)
        if summary:
            result.append(summary)

    return result
