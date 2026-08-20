"""Worker OT Summary — Government Compliance Report.

Shows monthly OT summary for all Workers:
- Employee info, Monthly salary, Hourly rate
- Total OT Hours worked in the month
- Govt-capped OT (max 15 hrs) at 2× rate
- Salary Slip OT amount
- Cash to Worker amount
- Sunday/Holiday hours breakdown

Run at month end for final government submission.
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
    columns = get_columns()
    summary = get_summary(data, year, month, is_month_complete)

    return columns, data, None, summary


def get_columns():
    """Columns for government OT summary."""
    return [
        {"label": "S.No", "fieldname": "sno", "fieldtype": "Int", "width": 45},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 80},
        {"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": "Dept", "fieldname": "department", "fieldtype": "Data", "width": 100},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Data", "width": 120},
        {"label": "Location", "fieldname": "location", "fieldtype": "Data", "width": 120},
        {"label": "Month Days", "fieldname": "days_in_month", "fieldtype": "Int", "width": 80},
        {"label": "Paid Days", "fieldname": "paid_days", "fieldtype": "Float", "width": 80, "precision": "1"},
        {"label": "Working Days", "fieldname": "qr_days", "fieldtype": "Int", "width": 90},
        {"label": "PH Days", "fieldname": "ph_days", "fieldtype": "Int", "width": 70},
        {"label": "LOP Days", "fieldname": "lop_days", "fieldtype": "Float", "width": 75, "precision": "1"},
        {"label": "/Month", "fieldname": "monthly_salary", "fieldtype": "Currency", "width": 100},
        {"label": "/Hour", "fieldname": "hourly_rate", "fieldtype": "Float", "width": 80, "precision": "2"},
        {"label": "Att.Salary", "fieldname": "att_salary", "fieldtype": "Currency", "width": 110},
        # OT columns
        {"label": "Total OT Hrs", "fieldname": "total_ot_hours_fmt", "fieldtype": "Data", "width": 90},
        {"label": "Total OT (1×)", "fieldname": "total_ot_amount_1x", "fieldtype": "Currency", "width": 110},
        {"label": "Govt OT Hrs (≤15)", "fieldname": "salary_slip_ot_hours_fmt", "fieldtype": "Data", "width": 120},
        {"label": "Govt OT Amt (2×)", "fieldname": "salary_slip_ot_amount_2x", "fieldtype": "Currency", "width": 120},
        {"label": "Cash to Worker", "fieldname": "cash_to_worker", "fieldtype": "Currency", "width": 120},
        {"label": "Total Earnings", "fieldname": "total_earnings", "fieldtype": "Currency", "width": 120},
        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 150},
    ]


def get_summary(data, year=None, month=None, is_month_complete=False):
    """Summary with totals for government submission."""
    if not data:
        return None

    total_workers = len(data)
    total_paid = sum(d.get("paid_days", 0) for d in data)
    total_ot_hours = sum(d.get("total_ot_hours", 0) for d in data)
    total_ot_1x = sum(d.get("total_ot_amount_1x", 0) for d in data)
    total_slip_2x = sum(d.get("salary_slip_ot_amount_2x", 0) for d in data)
    total_cash = sum(d.get("cash_to_worker", 0) for d in data)
    total_earnings = sum(d.get("total_earnings", 0) for d in data)
    total_att = sum(d.get("att_salary", 0) for d in data)

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
            f"Paid Days: {total_paid:.0f} | "
            f"Att.Salary: {frappe.format_currency(total_att)}<br>"
            f"<b>Total OT:</b> {fmt_hhmm(total_ot_hours)} = {frappe.format_currency(total_ot_1x)} (1×) | "
            f"<b>Govt OT (≤{GOV_OT_CAP_HOURS}h, 2×):</b> {frappe.format_currency(total_slip_2x)} | "
            f"<b>Cash:</b> {frappe.format_currency(total_cash)} | "
            f"<b>Total Earnings:</b> {frappe.format_currency(total_earnings)}<br>"
            f"<span style='color:#888;'>Rate: Salary / {days} days / {STANDARD_SHIFT} hrs | "
            f"Sunday/Holiday work = ALL hours as OT | Govt cap = {GOV_OT_CAP_HOURS} hrs/month</span><br>"
            f"<span style='color:{'green' if is_month_complete else 'orange'};'><b>Status: {month_status}</b></span>"
        )
    }
