import json

import frappe
from frappe.utils import getdate, now_datetime, time_diff_in_seconds

from elemental_erp.utils.mobile_access import PRODUCTION_FLOOR_ROLES
from elemental_erp.utils.transactions import assert_active_job, require_doc_permission
from elemental_erp.utils.worker_overtime import hourly_rate


SUPERVISOR_ROLES = ("Elemental Production HOD",)


def _require_supervisor():
	roles = set(frappe.get_roles())
	if "System Manager" not in roles and not roles.intersection(SUPERVISOR_ROLES):
		frappe.throw(
			"This action requires the Elemental Production HOD supervisor role.",
			frappe.PermissionError,
		)


def _resolve_employee(value):
	value = (value or "").strip()
	employee = frappe.db.get_value(
		"Employee",
		{"name": value},
		["name", "employee_name", "department", "status"],
		as_dict=True,
	)
	if not employee:
		employee = frappe.db.get_value(
			"Employee",
			{"employee_qr_value": value},
			["name", "employee_name", "department", "status"],
			as_dict=True,
		)
	if not employee or employee.status != "Active":
		frappe.throw("Active worker QR / Employee Code not recognised.")
	return employee


def _resolve_job(value):
	value = (value or "").strip()
	job = frappe.db.get_value(
		"Job", {"name": value}, ["name", "job_name", "status"], as_dict=True
	)
	if not job:
		job = frappe.db.get_value(
			"Job", {"job_qr_value": value}, ["name", "job_name", "status"], as_dict=True
		)
	if not job:
		frappe.throw("Job QR / Job Code not recognised.")
	assert_active_job(job.name)
	require_doc_permission(frappe.get_doc("Job", job.name), "read")
	return job


def _resolve_workstation(value):
	value = (value or "").strip()
	workstation = frappe.db.get_value(
		"Production Workstation",
		{"name": value},
		["name", "workstation_name", "workstation_type", "department", "status"],
		as_dict=True,
	)
	if not workstation:
		workstation = frappe.db.get_value(
			"Production Workstation",
			{"qr_value": value},
			["name", "workstation_name", "workstation_type", "department", "status"],
			as_dict=True,
		)
	if not workstation or workstation.status != "Active":
		frappe.throw("Active Machine / Table QR not recognised.")
	return workstation


def _require_gate_in(employee, at_time=None):
	at_time = at_time or now_datetime()
	last = frappe.db.get_value(
		"Employee Checkin",
		{"employee": employee, "time": ["between", [f"{getdate(at_time)} 00:00:00", at_time]]},
		["log_type", "time"],
		order_by="time desc",
		as_dict=True,
	)
	if not last or last.log_type != "IN":
		frappe.throw(f"Worker {employee} must complete Gate-In before Job work can start.")
	return last


def _close_log(log, status, end_time=None, remarks=None, closed_by=None):
	end_time = end_time or now_datetime()
	hours = max(time_diff_in_seconds(end_time, log.start_time) / 3600, 0)
	values = {
		"status": status,
		"active_employee_key": None,
		"end_time": end_time,
		"hours_spent": round(hours, 4),
		"labour_cost": round(hours * float(log.hourly_rate or 0), 2),
		"closed_by": closed_by or frappe.session.user,
		"close_action": status,
	}
	if remarks:
		values["remarks"] = remarks
	frappe.db.set_value("Worker Job Time Log", log.name, values)
	return frappe._dict({"name": log.name, **values})


@frappe.whitelist()
def lookup_workstation(value):
	_require_supervisor()
	return _resolve_workstation(value)


@frappe.whitelist()
def lookup_worker(value):
	_require_supervisor()
	employee = _resolve_employee(value)
	employee["gate_in"] = bool(_require_gate_in(employee.name))
	employee["active_log"] = frappe.db.get_value(
		"Worker Job Time Log", {"employee": employee.name, "status": "Active"}, "name"
	)
	return employee


@frappe.whitelist()
def lookup_job(value):
	_require_supervisor()
	return _resolve_job(value)


@frappe.whitelist()
def start_workers(workstation, job, employees):
	"""Start one immutable time segment per worker after Gate-In."""
	_require_supervisor()
	station = _resolve_workstation(workstation)
	job_doc = _resolve_job(job)
	if isinstance(employees, str):
		employees = json.loads(employees)
	employees = list(dict.fromkeys(employees or []))
	if not employees:
		frappe.throw("Scan at least one worker badge.")

	started_at = now_datetime()
	created = []
	for value in employees:
		employee = _resolve_employee(value)
		_require_gate_in(employee.name, started_at)
		active = frappe.db.sql(
			"SELECT name, job, workstation FROM `tabWorker Job Time Log` "
			"WHERE employee = %s AND status = 'Active' FOR UPDATE",
			employee.name,
			as_dict=True,
		)
		if active:
			frappe.throw(
				f"{employee.employee_name} already has active allocation {active[0].name} "
				f"on Job {active[0].job}. Hold or complete it before starting another Job."
			)
		rate = hourly_rate(employee.name, started_at.year, started_at.month)
		try:
			log = frappe.get_doc(
				{
					"doctype": "Worker Job Time Log",
					"employee": employee.name,
					"job": job_doc.name,
					"workstation": station.name,
					"department": station.department,
					"work_date": getdate(started_at),
					"status": "Active",
					"active_employee_key": employee.name,
					"start_time": started_at,
					"hourly_rate": rate,
					"started_by": frappe.session.user,
				}
			).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			frappe.throw(
				f"{employee.employee_name} was started by another supervisor at the same time. "
				"Reload active allocations before continuing."
			)
		created.append({"name": log.name, "employee": employee.name, "employee_name": employee.employee_name})
	frappe.db.commit()
	return {"job": job_doc.name, "workstation": station.name, "started": created}


@frappe.whitelist()
def close_workers(job, employees, action, remarks=None):
	_require_supervisor()
	job_doc = _resolve_job(job)
	if action not in ("Hold", "Completed"):
		frappe.throw("Close action must be Hold or Completed.")
	if isinstance(employees, str):
		employees = json.loads(employees)
	employees = list(dict.fromkeys(employees or []))
	if not employees:
		frappe.throw("Select at least one worker allocation to close.")
	closed = []
	for value in employees:
		employee = _resolve_employee(value)
		rows = frappe.db.sql(
			"SELECT name, employee, start_time, hourly_rate FROM `tabWorker Job Time Log` "
			"WHERE employee = %s AND job = %s AND status = 'Active' FOR UPDATE",
			(employee.name, job_doc.name),
			as_dict=True,
		)
		if not rows:
			frappe.throw(f"{employee.employee_name} has no active allocation on Job {job_doc.name}.")
		closed.append(_close_log(rows[0], action, remarks=remarks))
	frappe.db.commit()
	return {"job": job_doc.name, "action": action, "closed": closed}


def close_active_logs_for_gate_out(employee, end_time=None):
	"""Safety net used by Gate-Out so labour time never runs overnight."""
	rows = frappe.db.sql(
		"SELECT name, employee, start_time, hourly_rate FROM `tabWorker Job Time Log` "
		"WHERE employee = %s AND status = 'Active' FOR UPDATE",
		employee,
		as_dict=True,
	)
	return [
		_close_log(
			row,
			"Gate-Out Closed",
			end_time=end_time,
			remarks="Automatically closed because the worker scanned Gate-Out.",
			closed_by=frappe.session.user,
		)
		for row in rows
	]


def assert_no_active_logs_for_job(job):
	active = frappe.db.count("Worker Job Time Log", {"job": job, "status": "Active"})
	if active:
		frappe.throw(
			f"{active} worker allocation(s) are still active on Job {job}. "
			"The supervisor must Hold or Complete them before the Job can close or cancel."
		)


@frappe.whitelist()
def get_active_allocations(job=None, workstation=None):
	_require_supervisor()
	filters = {"status": "Active"}
	if job:
		filters["job"] = _resolve_job(job).name
	if workstation:
		filters["workstation"] = _resolve_workstation(workstation).name
	return frappe.get_all(
		"Worker Job Time Log",
		filters=filters,
		fields=["name", "employee", "employee_name", "job", "workstation", "department", "start_time"],
		order_by="start_time asc",
		limit_page_length=0,
	)
