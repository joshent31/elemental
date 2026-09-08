import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = _get_data(filters)
	return _columns(), data, None, _chart(data), _summary(data)


def _columns():
	return [
		{"label": "Job", "fieldname": "job", "fieldtype": "Link", "options": "Job", "width": 145},
		{"label": "Job Name", "fieldname": "job_name", "fieldtype": "Data", "width": 180},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 130},
		{"label": "Finished Good", "fieldname": "finished_good", "fieldtype": "Link", "options": "Finished Good", "width": 130},
		{"label": "FG Name", "fieldname": "fg_name", "fieldtype": "Data", "width": 180},
		{"label": "Part Code", "fieldname": "subpart_code", "fieldtype": "Data", "width": 110},
		{"label": "Subpart", "fieldname": "subpart_name", "fieldtype": "Data", "width": 170},
		{"label": "Process", "fieldname": "process_name", "fieldtype": "Data", "width": 120},
		{"label": "Lying Department", "fieldname": "lying_department", "fieldtype": "Data", "width": 180},
		{"label": "Movement", "fieldname": "transfer_status", "fieldtype": "Data", "width": 120},
		{"label": "Required Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 105},
		{"label": "Completed Qty", "fieldname": "completed_qty", "fieldtype": "Float", "width": 115},
		{"label": "Pending Qty", "fieldname": "pending_qty", "fieldtype": "Float", "width": 105},
		{"label": "Completion %", "fieldname": "completion_percent", "fieldtype": "Percent", "width": 110},
		{"label": "Tracker Status", "fieldname": "tracker_status", "fieldtype": "Data", "width": 110},
		{"label": "Last Movement", "fieldname": "last_movement_on", "fieldtype": "Datetime", "width": 155},
	]


def _get_data(filters):
	conditions = []
	values = {}
	for field in ("job", "finished_good", "process_name"):
		if filters.get(field):
			conditions.append(f"q.{field} = %({field})s")
			values[field] = filters[field]
	if filters.get("customer"):
		conditions.append("j.customer = %(customer)s")
		values["customer"] = filters.customer
	if filters.get("tracker_status"):
		conditions.append("q.status = %(tracker_status)s")
		values["tracker_status"] = filters.tracker_status
	if filters.get("year"):
		conditions.append("YEAR(COALESCE(j.start_date, DATE(j.creation))) = %(year)s")
		values["year"] = int(filters.year)
	if filters.get("month"):
		conditions.append("MONTH(COALESCE(j.start_date, DATE(j.creation))) = %(month)s")
		values["month"] = int(filters.month)

	where = " AND ".join(conditions) if conditions else "1=1"
	rows = frappe.db.sql(
		f"""SELECT q.name, q.job, j.job_name, j.customer, q.finished_good,
			fg.fg_name AS fg_name, q.subpart_code, q.subpart_name,
			q.process_name, q.total_qty, q.completed_qty, q.status AS tracker_status
		FROM `tabQR Code Master` q
		INNER JOIN `tabJob` j ON j.name = q.job
		LEFT JOIN `tabFinished Good` fg ON fg.name = q.finished_good
		WHERE {where}
		ORDER BY j.due_date, q.job, q.finished_good, q.idx, q.creation""",
		values,
		as_dict=True,
	)

	latest = {}
	tracker_names = [row.name for row in rows]
	if tracker_names:
		for transfer in frappe.get_all(
			"Department Transfer",
			filters={"qr_code_master": ["in", tracker_names], "status": ["!=", "Cancelled"]},
			fields=["qr_code_master", "from_department", "to_department", "status", "dispatched_on", "received_on", "creation"],
			order_by="creation asc",
		):
			latest[transfer.qr_code_master] = transfer

	data = []
	for row in rows:
		movement = latest.get(row.name)
		if movement:
			if movement.status in ("Received", "Qty Mismatch"):
				lying = movement.to_department
			else:
				lying = f"{movement.from_department} → {movement.to_department}"
			last_movement = movement.received_on or movement.dispatched_on or movement.creation
			transfer_status = movement.status
		else:
			lying = row.process_name or "Not Assigned"
			last_movement = None
			transfer_status = "Not Transferred"

		if filters.get("department") and filters.department not in (
			lying,
			movement.from_department if movement else None,
			movement.to_department if movement else None,
		):
			continue

		total = flt(row.total_qty)
		completed = min(flt(row.completed_qty), total) if total > 0 else flt(row.completed_qty)
		row.update(
			lying_department=lying,
			transfer_status=transfer_status,
			last_movement_on=last_movement,
			pending_qty=max(total - completed, 0),
			completion_percent=(completed / total * 100) if total else 0,
		)
		data.append(row)
	return data


def _summary(data):
	total = sum(flt(row.total_qty) for row in data)
	completed = sum(min(flt(row.completed_qty), flt(row.total_qty)) for row in data)
	return [
		{"label": "Trackers", "value": len(data), "indicator": "Blue"},
		{"label": "Required Qty", "value": total, "datatype": "Float"},
		{"label": "Pending Qty", "value": max(total - completed, 0), "datatype": "Float", "indicator": "Orange"},
		{"label": "Completion", "value": (completed / total * 100) if total else 0, "datatype": "Percent", "indicator": "Green"},
	]


def _chart(data):
	department_pending = {}
	for row in data:
		department_pending[row.lying_department] = department_pending.get(row.lying_department, 0) + flt(row.pending_qty)
	labels = list(department_pending)
	if not labels or not any(department_pending.values()):
		return None
	return {
		"data": {"labels": labels, "datasets": [{"name": "Pending Qty", "values": [department_pending[label] for label in labels]}]},
		"type": "bar",
		"colors": ["#f59e0b"],
	}
