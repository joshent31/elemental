"""Worker Attendance Report — Script Report.

Matches the PayRepWorkersAttn Excel format:
- Employee info (S.No, Location, Code, Name, Department, Designation)
- Monthly summary (Month days, Paid, QR, PH, LOP)
- Pay structure (Monthly salary, Hourly rate = Salary/Days/8, Attendance salary)
- OT summary:
    Total OT (1×) = OT Hours × Hourly Rate (company tracking)
    Salary Slip (2×) = Capped OT × Hourly Rate × 2 (govt required, on slip)
    Cash to Worker = Remaining OT value − half Salary Slip OT (never below zero)
- Daily columns (IN, OUT, OT Hrs, OT Amt, Job, Brand) per day

Run at month end when all checkin data is complete.
"""
import calendar
import frappe
from frappe.utils import fmt_money, getdate


def execute(filters=None):
    filters = filters or {}
    year = int(filters.get("year") or getdate().year)
    month = int(filters.get("month") or getdate().month)
    department = filters.get("department")
    employee_category = filters.get("employee_category") or "Worker"

    from elemental_erp.utils.worker_overtime import get_worker_attendance_report_data, get_days_in_month

    # Month-end completeness check
    days_in_month = get_days_in_month(year, month)
    today = getdate()
    is_month_complete = (
        (today.year > year) or
        (today.year == year and today.month > month) or
        (today.year == year and today.month == month and today.day >= days_in_month)
    )

    data = get_worker_attendance_report_data(year, month, department, employee_category=employee_category)
    columns = get_columns(year, month)
    summary = get_summary(data, year, month, is_month_complete)

    # Flatten daily data into each row
    for i, row in enumerate(data):
        row["sno"] = i + 1
        for day_info in row.get("daily_data", []):
            day = getdate(day_info["date"]).day
            prefix = f"d{day}"
            status = day_info.get("status", "")
            if status in ("A", "L", "PH", "W/O"):
                row[f"{prefix}_in"] = status
            elif status == "PH-Work":
                # Govt holiday with work — ALL hours = OT
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

    return columns, data, summary.get("message") if summary else None, get_chart(data)


def get_chart(data):
    if not data:
        return None
    top = sorted(data, key=lambda row: row.get("total_ot_hours", 0), reverse=True)[:15]
    return {
        "data": {
            "labels": [row.get("employee_name") or row.get("employee") for row in top],
            "datasets": [{"name": "Approved OT Hours", "values": [row.get("total_ot_hours", 0) for row in top]}],
        },
        "type": "bar",
        "colors": ["#1565c0"],
    }


def get_columns(year, month):
    """Build columns matching the Excel PayRepWorkersAttn format."""
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
        {"label": "/Hour (Sal/Days/8)", "fieldname": "hourly_rate", "fieldtype": "Float", "width": 120, "precision": "2"},
        {"label": "Att.Salary", "fieldname": "att_salary", "fieldtype": "Currency", "width": 100},
        # Total OT (at 1× rate — company tracking)
        {"label": "Approved OT Hrs", "fieldname": "total_ot_hours_fmt", "fieldtype": "Data", "width": 105},
        {"label": "Approved OT Value (1×)", "fieldname": "total_ot_amount_1x", "fieldtype": "Currency", "width": 145},
        # Salary Slip (at 2× rate — govt required, on slip)
        {"label": "Slip OT Hrs (≤15)", "fieldname": "salary_slip_ot_hours_fmt", "fieldtype": "Data", "width": 110},
        {"label": "Slip OT Amt (2×)", "fieldname": "salary_slip_ot_amount_2x", "fieldtype": "Currency", "width": 130},
        # Cash to Worker: remaining value less half of Salary Slip OT
        {"label": "Cash OT Hrs", "fieldname": "cash_ot_hours", "fieldtype": "Float", "width": 90, "precision": "2"},
        {"label": "Cash Gross (1×)", "fieldname": "cash_ot_value_before_adjustment", "fieldtype": "Currency", "width": 115},
        {"label": "Less Slip OT ÷ 2", "fieldname": "cash_salary_slip_adjustment", "fieldtype": "Currency", "width": 120},
        {"label": "Cash to Worker", "fieldname": "cash_to_worker", "fieldtype": "Currency", "width": 120},
        {"label": "Total OT Payable", "fieldname": "total_ot_payable", "fieldtype": "Currency", "width": 120},
        # Total Earnings
        {"label": "Total Earnings", "fieldname": "total_earnings", "fieldtype": "Currency", "width": 120},
    ]

    # Daily columns for each day of the month
    for day in range(1, days_in_month + 1):
        prefix = f"d{day}"
        columns.append({"label": f"{day} IN", "fieldname": f"{prefix}_in", "fieldtype": "Data", "width": 75})
        columns.append({"label": f"{day} OUT", "fieldname": f"{prefix}_out", "fieldtype": "Data", "width": 75})
        columns.append({"label": f"{day} OT", "fieldname": f"{prefix}_ot", "fieldtype": "Data", "width": 55})
        columns.append({"label": f"{day} Amt", "fieldname": f"{prefix}_amt", "fieldtype": "Currency", "width": 75})
        columns.append({"label": f"{day} Job", "fieldname": f"{prefix}_job", "fieldtype": "Data", "width": 80})
        columns.append({"label": f"{day} Brand", "fieldname": f"{prefix}_brand", "fieldtype": "Data", "width": 90})

    return columns


def get_summary(data, year=None, month=None, is_month_complete=False):
    """Summary row at the top showing totals + OT formula + month status."""
    if not data:
        return None

    total_paid = sum(d.get("paid_days", 0) for d in data)
    total_ph = sum(d.get("ph_days", 0) for d in data)
    total_lop = sum(d.get("lop_days", 0) for d in data)
    total_att_salary = sum(d.get("att_salary", 0) for d in data)
    total_ot_hours = sum(d.get("total_ot_hours", 0) for d in data)
    total_ot_1x = sum(d.get("total_ot_amount_1x", 0) for d in data)
    total_slip_2x = sum(d.get("salary_slip_ot_amount_2x", 0) for d in data)
    total_cash = sum(d.get("cash_to_worker", 0) for d in data)
    total_earnings = sum(d.get("total_earnings", 0) for d in data)

    def fmt_hhmm(hours):
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h}:{m:02d}"

    from elemental_erp.utils.worker_overtime import get_days_in_month, STANDARD_SHIFT, GOV_OT_CAP_HOURS
    days = get_days_in_month(year, month) if year and month else 31

    formula_msg = (
        f"Formula: Monthly Salary / {days} days / {STANDARD_SHIFT} hrs = Hourly Rate | "
        f"Total OT (1x) = OT Hrs x Rate | "
        f"Salary Slip = min(OT, {GOV_OT_CAP_HOURS} hrs) x Rate x 2 | "
        f"Cash = Remaining OT value - (Slip OT / 2), minimum zero"
    )

    month_status = "COMPLETE" if is_month_complete else "IN PROGRESS — run at month end for final data"

    return {
        "message": (
            f"<b>Workers: {len(data)}</b> | "
            f"Paid Days: {total_paid:.0f} | PH: {total_ph} | LOP: {total_lop:.0f} | "
            f"Att.Salary: {fmt_money(total_att_salary)}<br>"
            f"<b>Total OT:</b> {fmt_hhmm(total_ot_hours)} = <b>{fmt_money(total_ot_1x)}</b> (at 1x rate) | "
            f"<b>Salary Slip:</b> {fmt_money(total_slip_2x)} (at 2x rate, ≤{GOV_OT_CAP_HOURS} hrs) | "
            f"<b>Cash to Worker:</b> {fmt_money(total_cash)} | "
            f"<b>Total Earnings:</b> {fmt_money(total_earnings)}<br>"
            f"<span style='color:#888;'>{formula_msg}</span><br>"
            f"<span style='color:{'green' if is_month_complete else 'orange'};'><b>Month Status: {month_status}</b></span>"
        )
    }


def format_time(dt):
    """Format a full Frappe datetime as unambiguous 24-hour HH:MM."""
    if not dt:
        return ""
    try:
        from frappe.utils import get_datetime
        return get_datetime(dt).strftime("%H:%M")
    except Exception:
        return str(dt)
