"""Shared transaction invariants for Elemental ERP.

All server-side transaction entry points should use these helpers so a late
or malformed document cannot regress a Job or mutate another Job's trackers.
"""

import math

import frappe


TERMINAL_JOB_STATUSES = {"Closed", "Cancelled"}

JOB_STATUS_ORDER = {
	"Draft": 0,
	"Job Created": 10,
	"Indent Raised": 20,
	"In Purchase": 30,
	"In Production": 40,
	"In Packaging": 50,
	"Material Consumption Pending": 60,
	"Material Consumed": 70,
	"Dispatched": 80,
	"Installed": 90,
	"Closed": 100,
	"Cancelled": 100,
}

JOB_FG_STATUS_BY_JOB_STATUS = {
	"Job Created": "Pending",
	"Indent Raised": "In Purchase",
	"In Purchase": "In Purchase",
	"In Production": "In Production",
	"In Packaging": "In Packaging",
	"Material Consumption Pending": "In Packaging",
	"Material Consumed": "In Packaging",
	"Dispatched": "Dispatched",
	"Installed": "Dispatched",
	"Closed": "Dispatched",
}


def positive_quantity(value, label="Quantity"):
	"""Return a finite positive float or raise a validation error."""
	try:
		value = float(value)
	except (TypeError, ValueError):
		frappe.throw(f"{label} must be a number greater than zero.")
	if not math.isfinite(value) or value <= 0:
		frappe.throw(f"{label} must be a finite number greater than zero.")
	return value


def resolve_department(value):
	"""Return the canonical Department link for a legacy display name.

	ERPNext names company departments as ``<department_name> - <company abbr>``.
	Early Elemental Material Indents stored ``department`` as free text, so a
	value such as ``Wood`` must resolve to ``Wood - EF`` before it is compared
	with link fields on downstream documents. Ambiguous display names are left
	unchanged so transactions cannot be linked to the wrong company silently.
	"""
	value = (value or "").strip()
	if not value or frappe.db.exists("Department", value):
		return value
	matches = frappe.get_all(
		"Department",
		filters={"department_name": value},
		pluck="name",
		limit_page_length=2,
	)
	return matches[0] if len(matches) == 1 else value


def assert_active_job(job):
	"""Reject transactions against terminal or missing Jobs."""
	status = frappe.db.get_value("Job", job, "status")
	if not status:
		frappe.throw(f"Job {job} does not exist.", frappe.DoesNotExistError)
	if status in TERMINAL_JOB_STATUSES:
		frappe.throw(f"Job {job} is {status}; no further transactions are allowed.")
	return status


def advance_job_status(job, target_status):
	"""Advance a Job without allowing an older transaction to regress it."""
	current = assert_active_job(job)
	if target_status not in JOB_STATUS_ORDER:
		frappe.throw(f"Unknown Job status: {target_status}")
	if JOB_STATUS_ORDER.get(current, -1) < JOB_STATUS_ORDER[target_status]:
		frappe.db.set_value("Job", job, "status", target_status)
		fg_status = JOB_FG_STATUS_BY_JOB_STATUS.get(target_status)
		if fg_status:
			frappe.db.sql(
				"UPDATE `tabJob FG Item` SET status = %s WHERE parent = %s",
				(fg_status, job),
			)
		return target_status
	return current


def assert_qr_belongs_to_job(qr_code_master, job):
	"""Return QR details after verifying that it belongs to ``job``."""
	qr = frappe.db.get_value(
		"QR Code Master",
		qr_code_master,
		[
			"name",
			"job",
			"finished_good",
			"subpart_code",
			"subpart_name",
			"total_qty",
			"completed_qty",
			"status",
			"process_name",
		],
		as_dict=True,
	)
	if not qr:
		frappe.throw(f"QR Code Master {qr_code_master} does not exist.", frappe.DoesNotExistError)
	if qr.job != job:
		frappe.throw(f"QR Code Master {qr.name} belongs to Job {qr.job}, not {job}.")
	return qr


def assert_subpart_label_belongs_to_job(label_name, job):
	"""Return label details after verifying that it belongs to ``job``."""
	label = frappe.db.get_value(
		"Job Subpart Label",
		label_name,
		["name", "job", "finished_good", "subpart_code", "subpart_name", "total_qty"],
		as_dict=True,
	)
	if not label:
		frappe.throw(f"Job Subpart Label {label_name} does not exist.", frappe.DoesNotExistError)
	if label.job != job:
		frappe.throw(f"Job Subpart Label {label.name} belongs to Job {label.job}, not {job}.")
	return label


def require_doc_permission(doc, permission="write"):
	"""Enforce normal Frappe permissions before internal bypassed writes."""
	if frappe.session.user == "Administrator":
		return
	doc.check_permission(permission)
