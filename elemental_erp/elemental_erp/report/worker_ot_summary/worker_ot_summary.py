"""Worker OT Summary — Government Compliance Report.

Simplified report for government submission:
- Employee info
- Daily OT hours for each day of the month
- Total OT hours (capped at 15 hrs max)
- NO cash column (government doesn't need this)
- Shows actual hours worked per day, total cannot exceed 15

Sunday/Holiday work = ALL hours are OT
Normal day = only hours beyond 8 are OT
"""
import calendar
import frappe
from frappe.utils import getdate


def execute(filters=None):
    filters = filters or {}
    year = filters.get("year") or getdate().year
    month = filters.get("month") or getdate().month
    department = filters.get("department")

    from elemental_erp.utils.worker_overtime import (
        get_worker_attendance_report_data, get_days_in_month,
        GOV_OT_CAP_HOURS, STANDARD_SHIFT,
    )

    days_in_month = get_days_in_month(year, month)
    today = getdate()
    is_month_complete = (
        (today.year > year) or
        (today.year == year and today.month > month) or
        (today.year == year and today.month == month and today.day >= days_in_month)
    )

    data = get_worker_attendance_report_data(year, month, department)
    columns = get_columns(year, month)
    summary = get_summary(data, year, month, is_month_complete)

    # Add daily OT columns to each row
    for row in data:
        for day_info in row.get("daily_data", []):
            day = getdate(day_info["date"]).day
            prefix = f"d{day}"
            status = day_info.get("status", "")
            ot_hrs = day_info.get("ot_hours", 0)

            if status in ("A", "L", "PH", "W/O"):
                row[f"{prefix}_ot"] = "—"
            elif status == "PH-Work":
                # Govt holiday with work — show actual hours as OT
                if ot_hrs > 0:
                    h = int(ot_hrs)
                    m = int(round((ot_hrs - h) * 60))
                    row[f"{prefix}_ot"] = f"{h}:{m:02d}"
                else:
                    row[f"{prefix}_ot"] = "—"
            else:
                # Normal day — show OT hours (beyond 8)
                if ot_hrs > 0:
                    h = int(ot_hrs)
                    m = int(round((ot_hrs - h) * 60))
                    row[f"{prefix}_ot"] = f"{h}:{m:02d}"
                else:
                    row[f"{prefix}_ot"] = "—"

        # Government-capped OT (max 15 hrs)
        row["govt_ot_hours"] = min(row.get("total_ot_hours", 0), GOV_OT_CAP_HOURS)
        govt_h = int(row["govt_ot_hours"])
        govt_m = int(round((row["govt_ot_hours"] - govt_h) * 60))
        row["govt_ot_hours_fmt"] = f"{govt_h}:{govt_m:02d}"

    return columns, data, None, summary


def get_columns(year, month):
    """Columns for government report — daily OT + total capped at 15."""
    days_in_month = calendar.monthrange(year, month)[1]

    columns = [
        {"label": "S.No", "fieldname": "sno", "fieldtype": "Int", "width": 45},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 80},
        {"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": "Dept", "fieldname": "department", "fieldtype": "Data", "width": 100},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Data", "width": 120},
        {"label": "Location", "fieldname": "location", "fieldtype": "Data", "width": 120},
        {"label": "Month Days", "fieldname": "days_in_month", "fieldtype": "Int", "width": 80},
        {"label": "Paid Days", "fieldname": "paid_days", "fieldtype": "Float", "width": 80, "precision": "1"},
        {"label": "Total OT Hrs", "fieldname": "total_ot_hours_fmt", "fieldtype": "Data", "width": 90},
        {"label": "Govt OT (≤15h)", "fieldname": "govt_ot_hours_fmt", "fieldtype": "Data", "width": 100},
    ]

    # Daily OT columns — one per day
    for day in range(1, days_in_month + 1):
        prefix = f"d{day}"
        columns.append({"label": f"{day}", "fieldname": f"{prefix}_ot", "fieldtype": "Data", "width": 55})

    return columns


def get_summary(data, year=None, month=None, is_month_complete=False):
    """Summary for government — total OT hours across all workers."""
    if not data:
        return None

    total_workers = len(data)
    total_ot_hours = sum(d.get("total_ot_hours", 0) for d in data)
    total_govt_ot = sum(min(d.get("total_ot_hours", 0), 15) for d in data)

    def fmt_hhmm(hours):
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h}:{m:02d}"

    from elemental_erp.utils.worker_overtime import get_days_in_month, STANDARD_SHIFT, GOV_OT_CAP_HOURS
    days = get_days_in_month(year, month) if year and month else 31

    month_status = "COMPLETE" if is_month_complete else "IN PROGRESS"

    return {
        "message": (
            f"<b>Workers: {total_workers}</b> | "
            f"<b>Total OT (actual):</b> {fmt_hhmm(total_ot_hours)} | "
            f"<b>Govt OT (capped ≤{GOV_OT_CAP_HOURS}h):</b> {fmt_hhmm(total_govt_ot)}<br>"
            f"<span style='color:#888;'>OT = Hours worked beyond {STANDARD_SHIFT}h/day | "
            f"Sunday/Holiday work = ALL hours as OT | "
            f"Govt max = {GOV_OT_CAP_HOURS} hrs/month</span><br>"
            f"<span style='color:{'green' if is_month_complete else 'orange'};'><b>Status: {month_status}</b></span>"
        )
    }
