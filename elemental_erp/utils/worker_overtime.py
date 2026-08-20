"""Worker Overtime calculation engine.

For Worker-category employees, this module:
1. Computes daily OT hours from Employee Checkin (IN/OUT pairs)
2. Applies the government cap of 15 OT hours/month
3. Splits OT into Salary Slip portion (12 hrs × 2× rate) and Cash portion
4. Generates a summary suitable for the Worker Attendance Report

OT Rate Formula (from client):
    Daily Rate  = Monthly Salary / Days in Month
    Hourly Rate = Daily Rate / 8
    Example: 16913 / 31 / 8 = 68.20 (for July with 31 days)
             16913 / 30 / 8 = 70.47 (for June with 30 days)
             16913 / 28 / 8 = 75.50 (for Feb with 28 days)

Government Rules:
    - Standard shift = 8 hours per day
    - Hours beyond 8 = Overtime
    - Max OT per month = 15 hours (government cap)
    - OT Rate = 2 × Hourly Rate
    - Salary Slip: 12 OT hours × 2× rate
    - Cash payment: remaining 3 OT hours × 2× rate (15 - 12 = 3)
"""
import calendar
import frappe
from frappe.utils import getdate, time_diff_in_hours


# Government OT cap per month
GOV_OT_CAP_HOURS = 15
# Of the 15 hrs, how many go on the salary slip
SALARY_SLIP_OT_HOURS = 12
# Cash OT = GOV_OT_CAP - SALARY_SLIP_OT
CASH_OT_HOURS = GOV_OT_CAP_HOURS - SALARY_SLIP_OT_HOURS
# Standard shift
STANDARD_SHIFT = 8


def get_days_in_month(year, month):
    """Get actual calendar days in the month (28, 29, 30, or 31)."""
    return calendar.monthrange(year, month)[1]


def hourly_rate(employee, year=None, month=None):
    """Compute hourly rate for a Worker.

    Formula: Monthly Salary / Days in Month / 8

    Example for employee with salary 16913:
        July (31 days):   16913 / 31 / 8 = 68.20
        June (30 days):   16913 / 30 / 8 = 70.47
        Feb (28 days):    16913 / 28 / 8 = 75.50
    """
    emp = frappe.db.get_value(
        "Employee", employee,
        ["ctc", "employee_category"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return 0

    ctc = emp.ctc or 0
    if not year or not month:
        today = getdate()
        year = today.year
        month = today.month

    days = get_days_in_month(year, month)
    denominator = days * STANDARD_SHIFT  # e.g. 31 * 8 = 248
    return ctc / denominator if denominator else 0


def daily_rate(employee, year=None, month=None):
    """Daily Rate = Monthly Salary / Days in Month.

    Example for employee with salary 16913:
        July (31 days): 16913 / 31 = 545.58
        June (30 days): 16913 / 30 = 563.77
    """
    emp = frappe.db.get_value("Employee", employee, ["ctc", "employee_category"], as_dict=True)
    if not emp or emp.employee_category != "Worker":
        return 0

    ctc = emp.ctc or 0
    if not year or not month:
        today = getdate()
        year = today.year
        month = today.month

    days = get_days_in_month(year, month)
    return ctc / days if days else 0


def compute_daily_ot(employee, date):
    """Compute OT hours for a single day from Employee Checkin records.

    Returns dict with in_time, out_time, total_hours, ot_hours, ot_amount.
    OT = Total Hours - 8 (standard shift).
    """
    emp = frappe.db.get_value(
        "Employee", employee,
        ["employee_category", "standard_shift_hours", "ctc"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return None

    shift = emp.standard_shift_hours or STANDARD_SHIFT

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

    date_obj = getdate(date)
    hr = hourly_rate(employee, date_obj.year, date_obj.month)
    ot_amount = round(ot_hours * hr, 2)

    return {
        "in_time": in_time,
        "out_time": out_time,
        "total_hours": total_hours,
        "ot_hours": ot_hours,
        "ot_amount": ot_amount,
        "status": "P",
    }


def compute_monthly_summary(employee, year, month):
    """Compute full monthly OT summary for a Worker.

    Returns dict with all fields needed for the report.
    This should be run at month end when all checkin data is complete.
    """
    emp = frappe.db.get_value(
        "Employee", employee,
        ["employee_name", "department", "designation", "ctc",
         "employee_category", "standard_shift_hours", "company",
         "branch"],
        as_dict=True,
    )
    if not emp or emp.employee_category != "Worker":
        return None

    shift = emp.standard_shift_hours or STANDARD_SHIFT
    days_in_month = get_days_in_month(year, month)
    hr = hourly_rate(employee, year, month)
    dr = daily_rate(employee, year, month)

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

    # Check for approved leaves
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
        end = getdate(leave.to_date)
        while d <= end:
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
        is_weekend = date_obj.weekday() >= 5

        if str(date_obj) in holiday_dates:
            daily_data.append({"date": date_str, "status": "PH", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            ph_days += 1
            continue

        if str(date_obj) in leave_dates:
            daily_data.append({"date": date_str, "status": "L", "in_time": None, "out_time": None, "ot_hours": 0, "ot_amount": 0, "job": "", "brand": ""})
            continue

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

    # Apply government cap (max 15 OT hrs/month)
    capped_ot_hours = min(total_ot_hours, GOV_OT_CAP_HOURS)
    salary_slip_ot_hours = min(capped_ot_hours, SALARY_SLIP_OT_HOURS)
    cash_ot_hours = max(capped_ot_hours - salary_slip_ot_hours, 0)

    # OT amounts at 2× hourly rate
    salary_slip_ot_amount = round(salary_slip_ot_hours * hr * 2, 2)
    cash_ot_amount = round(cash_ot_hours * hr * 2, 2)
    total_ot_amount_capped = round(capped_ot_hours * hr * 2, 2)

    # Attendance salary = paid days × daily rate
    att_salary = round(paid_days * dr, 2)

    # Total earnings = attendance salary + OT (at 2× rate)
    total_earnings = round(att_salary + total_ot_amount_capped, 2)

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
        "days_in_month": days_in_month,
        "hourly_rate": round(hr, 2),
        "daily_rate": round(dr, 2),
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

    This should be run at month end when all checkin data is complete.
    Returns list of monthly summaries sorted by department, name.
    """
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
