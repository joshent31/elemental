import frappe
from frappe.utils import flt, getdate, nowdate


PROCESSES = ("Metal", "Wood", "Electrical", "Powdercoating", "Paint", "US Assembly", "Packing")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = _get_data(filters)
	return _columns(), data, None, _chart(data), _summary(data)


def _columns():
	columns = [
		{"label": "Job", "fieldname": "job", "fieldtype": "Link", "options": "Job", "width": 145},
		{"label": "Job Name", "fieldname": "job_name", "fieldtype": "Data", "width": 190},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 130},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": "Days Left", "fieldname": "days_left", "fieldtype": "Int", "width": 85},
		{"label": "FG Count", "fieldname": "fg_count", "fieldtype": "Int", "width": 85},
		{"label": "Production Completion %", "fieldname": "completion_percent", "fieldtype": "Percent", "width": 155},
	]
	for process in PROCESSES:
		columns.append({"label": f"{process} %", "fieldname": _fieldname(process), "fieldtype": "Percent", "width": 115})
	columns.extend([
		{"label": "Required Process Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 135},
		{"label": "Completed Process Qty", "fieldname": "completed_qty", "fieldtype": "Float", "width": 145},
		{"label": "Pending Process Qty", "fieldname": "pending_qty", "fieldtype": "Float", "width": 135},
	])
	return columns


def _fieldname(process):
	return f"{process.lower().replace(' ', '_')}_percent"


def _get_data(filters):
	conditions, values = [], {}
	for field in ("job", "customer", "status"):
		if filters.get(field):
			column = "j.name" if field == "job" else f"j.{field}"
			conditions.append(f"{column} = %({field})s")
			values[field] = filters[field]
	if filters.get("year"):
		conditions.append("YEAR(COALESCE(j.start_date, DATE(j.creation))) = %(year)s")
		values["year"] = int(filters.year)
	if filters.get("month"):
		conditions.append("MONTH(COALESCE(j.start_date, DATE(j.creation))) = %(month)s")
		values["month"] = int(filters.month)
	where = " AND ".join(conditions) if conditions else "1=1"
	jobs = frappe.db.sql(
		f"""SELECT j.name AS job, j.job_name, j.customer, j.status, j.start_date, j.due_date,
			COUNT(DISTINCT fgi.name) AS fg_count
		FROM `tabJob` j
		LEFT JOIN `tabJob FG Item` fgi ON fgi.parent = j.name AND fgi.parenttype = 'Job'
		WHERE {where}
		GROUP BY j.name
		ORDER BY j.due_date, j.creation DESC""",
		values,
		as_dict=True,
	)
	job_names = [row.job for row in jobs]
	aggregates = {}
	if job_names:
		for tracker in frappe.get_all(
			"QR Code Master",
			filters={"job": ["in", job_names]},
			fields=["job", "process_name", "total_qty", "completed_qty"],
		):
			job_data = aggregates.setdefault(tracker.job, {"total": 0.0, "completed": 0.0, "processes": {}})
			total = flt(tracker.total_qty)
			completed = min(flt(tracker.completed_qty), total) if total > 0 else flt(tracker.completed_qty)
			job_data["total"] += total
			job_data["completed"] += completed
			process_data = job_data["processes"].setdefault(tracker.process_name, [0.0, 0.0])
			process_data[0] += total
			process_data[1] += completed

	today = getdate(nowdate())
	for row in jobs:
		aggregate = aggregates.get(row.job, {"total": 0.0, "completed": 0.0, "processes": {}})
		total, completed = aggregate["total"], aggregate["completed"]
		row.update(
			required_qty=total,
			completed_qty=completed,
			pending_qty=max(total - completed, 0),
			completion_percent=(completed / total * 100) if total else 0,
			days_left=(getdate(row.due_date) - today).days if row.due_date else None,
		)
		for process in PROCESSES:
			process_total, process_completed = aggregate["processes"].get(process, (0, 0))
			row[_fieldname(process)] = (process_completed / process_total * 100) if process_total else 0
	return jobs


def _summary(data):
	total = sum(flt(row.required_qty) for row in data)
	completed = sum(flt(row.completed_qty) for row in data)
	overdue = sum(1 for row in data if row.days_left is not None and row.days_left < 0 and row.completion_percent < 100)
	return [
		{"label": "Jobs", "value": len(data), "indicator": "Blue"},
		{"label": "Overall Production Completion", "value": (completed / total * 100) if total else 0, "datatype": "Percent", "indicator": "Green"},
		{"label": "Pending Process Qty", "value": max(total - completed, 0), "datatype": "Float", "indicator": "Orange"},
		{"label": "Overdue Jobs", "value": overdue, "indicator": "Red" if overdue else "Green"},
	]


def _chart(data):
	rows = data[:20]
	if not rows or not any(flt(row.completion_percent) for row in rows):
		return None
	return {
		"data": {"labels": [row.job for row in rows], "datasets": [{"name": "Production Completion %", "values": [flt(row.completion_percent, 2) for row in rows]}]},
		"type": "bar",
		"colors": ["#2563eb"],
	}
