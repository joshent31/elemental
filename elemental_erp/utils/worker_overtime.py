"""Worker Overtime calculation engine.

Business Logic (from client's Excel PayRepWorkersAttn):
=========================================================

Standard Shift: 9 AM to 6 PM = 8 working hours/day
OT = Any hours beyond 8 per day

Government Rules:
- Max OT per month = 15 hours (for government report)
- OT Rate = 2 × Hourly Rate (as per govt norm)

OT Rate Formula:
    Daily Rate  = Monthly Salary / Days in Month
    Hourly Rate = Daily Rate / 8
    Example: 16913 / 31 / 8 = 68.20 (for July with 31 days)

Report Columns:
1. Total OT Hours    = Sum of all daily OT hours in the month
2. Total OT Amount   = Total OT Hours × Hourly Rate (at 1× rate)
                       This is what the company tracks internally
3. Salary Slip Hours = min(Total OT, 15) — government capped
4. Salary Slip Amount = Salary Slip Hours × Hourly Rate × 2 (at 2× rate)
                       This goes on the salary slip
5. Cash to Worker    = Total OT Amount (1×) − Salary Slip Amount (2×)
                       The difference is paid in cash to the worker
6. Total Earnings    = Attendance Salary + Total OT Amount (1×)

Example (Worker with salary 16913, July 31 days):
    Hourly Rate = 16913 / 31 / 8 = 68.20
    If worker works 60.5 OT hours in the month:
    - Total OT Amount  = 60.5 × 68.20 = 4126.10 (at 1×)
    - Salary Slip (15 hrs capped) = 15 × 68.20 × 2 = 2046.00 (at 2×)
    - Cash to Worker   = 4126.10 − 2046.00 = 2080.10
    - Total Earnings   = Att.Salary + 4126.10
"""
import calendar
import frappe
from frappe.utils import getdate, time_diff_in_hours


# Government OT cap per month
GOV_OT_CAP_HOURS = 15
# Standard shift = 8 working hours
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
    """Daily Rate = Monthly Salary / Days in Month."""
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

    Standard shift = 8 hours. Hours beyond 8 = OT.
    Returns dict with in_time, out_time, total_hours, ot_hours, ot_amount.
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

    Report columns:
    - Total OT Hours: sum of all daily OT hours
    - Total OT Amount: OT Hours × Hourly Rate (at 1× rate)
    - Salary Slip Hours: min(Total OT, 15) — govt capped
    - Salary Slip Amount: Salary Slip Hours × Hourly Rate × 2 (at 2× rate)
    - Cash to Worker: Total OT Amount (1×) − Salary Slip Amount (2×)
    - Total Earnings: Attendance Salary + Total OT Amount (1×)
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

    # === OT Calculations ===
    # Total OT Amount = OT Hours × Hourly Rate (at 1× rate)
    # This is what the company tracks internally
    total_ot_amount_1x = round(total_ot_hours * hr, 2)

    # Government cap: max 15 OT hours per month
    capped_ot_hours = min(total_ot_hours, GOV_OT_CAP_HOURS)

    # Salary Slip = Capped OT Hours × Hourly Rate × 2 (at 2× rate)
    # This goes on the salary slip as per govt norm
    salary_slip_ot_amount = round(capped_ot_hours * hr * 2, 2)

    # Cash to Worker = Total OT Amount (1×) − Salary Slip Amount (2×)
    # The difference is paid in cash
    cash_to_worker = round(total_ot_amount_1x - salary_slip_ot_amount, 2)

    # Attendance Salary = Paid Days × Daily Rate
    att_salary = round(paid_days * dr, 2)

    # Total Earnings = Att.Salary + Total OT Amount (1×)
    total_earnings = round(att_salary + total_ot_amount_1x, 2)

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
        # Total OT (at 1× rate — company tracking)
        "total_ot_hours": total_ot_hours,
        "total_ot_hours_fmt": format_hhmm(total_ot_hours),
        "total_ot_amount_1x": total_ot_amount_1x,
        # Salary Slip (at 2× rate — govt required)
        "salary_slip_ot_hours": capped_ot_hours,
        "salary_slip_ot_hours_fmt": format_hhmm(capped_ot_hours),
        "salary_slip_ot_amount_2x": salary_slip_ot_amount,
        # Cash to Worker (difference)
        "cash_to_worker": cash_to_worker,
        # Total Earnings
        "total_earnings": total_earnings,
        "daily_data": daily_data,
    }


def get_worker_attendance_report_data(year, month, department=None, location=None):
    """Get all Worker-category employees' attendance data for the report.

    Run at month end when all checkin data is complete.
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
