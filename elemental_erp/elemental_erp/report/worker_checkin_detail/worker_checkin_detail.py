"""Worker Checkin Detail Report — Shows ALL entries and exits per day.

This report shows every individual IN/OUT scan for each worker per day,
not just first-in and last-out. Useful for tracking multiple entries/exits.

Columns:
- Employee, Name, Department
- Date
- Entry 1 (IN/OUT), Entry 2, Entry 3, etc.
- First IN time, Last OUT time
- Total Span (last OUT - first IN)
- OT Hours (based on span)
- Source (Gate Scan / Manual Attendance)
"""
import calendar
import frappe
from frappe.utils import getdate, time_diff_in_hours


def execute(filters=None):
    filters = filters or {}
    year = int(filters.get("year") or getdate().year)
    month = int(filters.get("month") or getdate().month)
    employee = filters.get("employee")
    department = filters.get("department")
    employee_category = filters.get("employee_category")

    days_in_month = calendar.monthrange(year, month)[1]
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{days_in_month}"

    # Get workers — filter by employee_category only if the custom field exists
    emp_filters = {}
    has_category = frappe.db.has_column("Employee", "employee_category")
    if has_category and employee_category:
        emp_filters["employee_category"] = employee_category
    if employee:
        emp_filters["name"] = employee
    if department:
        emp_filters["department"] = department

    workers = frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_name", "department", "designation"],
        order_by="department asc, employee_name asc",
    )

    columns = get_columns()
    data = []

    for idx, emp in enumerate(workers):
        for day in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            row = build_day_row(emp, date_str, idx + 1)
            if row:
                data.append(row)

    return columns, data, None, get_chart(data)


def get_chart(data):
    if not data:
        return None
    totals = {}
    labels = {}
    for row in data:
        employee = row.get("employee")
        totals[employee] = totals.get(employee, 0) + (row.get("ot_hours") or 0)
        labels[employee] = row.get("employee_name") or employee
    top = sorted(totals, key=totals.get, reverse=True)[:15]
    values = [round(float(totals[key] or 0), 2) for key in top]
    if not any(values):
        return None
    return {
        "data": {"labels": [labels[key] for key in top], "datasets": [{"name": "Recorded OT Hours", "values": values}]},
        "type": "bar",
        "colors": ["#7b61ff"],
    }


def build_day_row(emp, date_str, sno):
    """Build one row per worker per day with all checkin/checkout entries."""

    # Get ALL Employee Checkin records for this day
    checkins = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": emp.name,
            "time": ["between", [f"{date_str} 00:00:00", f"{date_str} 23:59:59"]],
        },
        fields=["log_type", "time", "employee", "latitude", "longitude",
                "checkin_photo", "checkin_address", "checkin_source"],
        order_by="time asc",
    )

    # Check for manual Attendance
    manual_att = None
    source = "Gate Scan"
    if not checkins:
        manual_att = frappe.db.get_value(
            "Attendance",
            {"employee": emp.name, "attendance_date": date_str},
            ["in_time", "out_time", "working_hours", "status"],
            as_dict=True,
        )
        if manual_att and manual_att.in_time:
            source = "Manual Attendance"
            # Create virtual entries from manual attendance
            checkins = []
            if manual_att.in_time:
                checkins.append({"log_type": "IN", "time": manual_att.in_time})
            if manual_att.out_time:
                checkins.append({"log_type": "OUT", "time": manual_att.out_time})

    if not checkins and not manual_att:
        return None

    # Determine first IN, last OUT
    in_times = [c["time"] for c in checkins if c["log_type"] == "IN"]
    out_times = [c["time"] for c in checkins if c["log_type"] == "OUT"]

    first_in = min(in_times) if in_times else None
    last_out = max(out_times) if out_times else None

    # Total span
    total_hours = 0
    if first_in and last_out:
        total_hours = round(time_diff_in_hours(last_out, first_in), 2)

    # OT: span - 8 hours (or full span on Sunday/Holiday)
    date_obj = getdate(date_str)
    # Saturday is a normal working day; only Sunday is weekly off.
    is_weekend = date_obj.weekday() == 6

    # Check for holiday
    holiday_list = frappe.db.get_value("Employee", emp.name, "holiday_list")
    is_holiday = False
    if holiday_list:
        is_holiday = frappe.db.exists(
            "Holiday",
            {"parent": holiday_list, "holiday_date": date_str},
        )

    if is_weekend or is_holiday:
        ot_hours = total_hours  # ALL hours on Sunday/Holiday
    else:
        ot_hours = max(total_hours - 8, 0)

    ot_hours = round(ot_hours, 2)

    # Build 24-hour entry strings: "IN 09:00 → OUT 13:30 → IN 14:15 → OUT 18:45"
    entry_parts = []
    has_photo = False
    gps_info = ""
    source_info = ""
    address_info = ""
    for c in checkins:
        t = format_time(c["time"])
        entry_parts.append(f"{c['log_type']} {t}")
        if c.get("checkin_photo"):
            has_photo = True
        if c.get("latitude") and c.get("longitude"):
            gps_info = f"{c['latitude']:.6f}, {c['longitude']:.6f}"
        if c.get("checkin_source") and not source_info:
            source_info = c["checkin_source"]
        if c.get("checkin_address") and not address_info:
            address_info = c["checkin_address"]

    entries_str = " → ".join(entry_parts) if entry_parts else ""

    # Count IN/OUT pairs
    in_count = len(in_times)
    out_count = len(out_times)

    # Day type
    day_type = "Working"
    if is_weekend:
        day_type = "Sunday/WO"
    elif is_holiday:
        day_type = "Holiday"

    return {
        "sno": sno,
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "designation": emp.designation,
        "date": date_str,
        "day": getdate(date_str).strftime("%a"),
        "day_type": day_type,
        "source": source_info or source,
        "entries": entries_str,
        "entry_count": in_count + out_count,
        "first_in": format_time(first_in),
        "last_out": format_time(last_out),
        "total_hours": total_hours,
        "ot_hours": ot_hours,
        "ot_hours_fmt": format_hhmm(ot_hours),
        "in_count": in_count,
        "out_count": out_count,
        "has_photo": "📸" if has_photo else "",
        "gps": gps_info,
        "address": address_info,
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


def format_hhmm(hours):
    """Format decimal hours to H:MM."""
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}:{m:02d}"


def get_columns():
    """Columns for the report."""
    return [
        {"label": "S.No", "fieldname": "sno", "fieldtype": "Int", "width": 45},
        {"label": "Code", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 70},
        {"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
        {"label": "Dept", "fieldname": "department", "fieldtype": "Data", "width": 90},
        {"label": "Desg", "fieldname": "designation", "fieldtype": "Data", "width": 90},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 90},
        {"label": "Day", "fieldname": "day", "fieldtype": "Data", "width": 45},
        {"label": "Type", "fieldname": "day_type", "fieldtype": "Data", "width": 80},
        {"label": "Source", "fieldname": "source", "fieldtype": "Data", "width": 100},
        {"label": "All Entries (IN → OUT → IN → ...)", "fieldname": "entries", "fieldtype": "Small Text", "width": 350},
        {"label": "Scans", "fieldname": "entry_count", "fieldtype": "Int", "width": 45},
        {"label": "1st IN", "fieldname": "first_in", "fieldtype": "Data", "width": 80},
        {"label": "Last OUT", "fieldname": "last_out", "fieldtype": "Data", "width": 80},
        {"label": "Span (hrs)", "fieldname": "total_hours", "fieldtype": "Float", "width": 75, "precision": "2"},
        {"label": "OT (hrs)", "fieldname": "ot_hours", "fieldtype": "Float", "width": 65, "precision": "2"},
        {"label": "OT", "fieldname": "ot_hours_fmt", "fieldtype": "Data", "width": 55},
        {"label": "INs", "fieldname": "in_count", "fieldtype": "Int", "width": 40},
        {"label": "OUTs", "fieldname": "out_count", "fieldtype": "Int", "width": 40},
        {"label": "", "fieldname": "has_photo", "fieldtype": "Data", "width": 30},
        {"label": "GPS Location", "fieldname": "gps", "fieldtype": "Data", "width": 160},
        {"label": "Site Address", "fieldname": "address", "fieldtype": "Small Text", "width": 200},
    ]
