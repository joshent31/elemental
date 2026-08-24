import hashlib

import frappe
from frappe.model.document import Document

from elemental_erp.utils.qr_generator import generate_qr_image


class JobSubpartLabel(Document):
	def validate(self):
		self.label_key = make_label_key(self.job, self.finished_good, self.subpart_code)
		if float(self.total_qty or 0) <= 0:
			frappe.throw("Job Subpart Label total quantity must be greater than zero.")
		for row in self.processes:
			qr = frappe.db.get_value(
				"QR Code Master",
				row.qr_code_master,
				["job", "finished_good", "subpart_code", "process_name"],
				as_dict=True,
			)
			if not qr:
				frappe.throw(f"Process tracker {row.qr_code_master} does not exist.")
			if (qr.job, qr.finished_good, qr.subpart_code) != (
				self.job,
				self.finished_good,
				self.subpart_code,
			):
				frappe.throw(
					f"Process tracker {row.qr_code_master} does not belong to this Job subpart."
				)
			if qr.process_name != row.process_name:
				frappe.throw(
					f"Process tracker {row.qr_code_master} is for {qr.process_name}, not {row.process_name}."
				)


def make_label_key(job, finished_good, subpart_code):
	identity = f"{job}|{finished_good}|{subpart_code}".encode()
	return hashlib.sha256(identity).hexdigest()


def _find_subpart(finished_good, subpart_code):
	for subpart in finished_good.subparts:
		if subpart.get("part_code") == subpart_code:
			return subpart
	return None


def _job_qty(job, finished_good):
	return frappe.db.get_value(
		"Job FG Item",
		{"parent": job, "finished_good": finished_good},
		"job_qty",
	) or 0


def _process_names(raw):
	if not raw:
		return ["US Assembly"]
	if isinstance(raw, (list, tuple)):
		processes = raw
	else:
		processes = raw.split("\n") if "\n" in raw else raw.split(",")
	return list(dict.fromkeys(process.strip() for process in processes if process.strip()))


def create_or_update_label(job, finished_good, subpart_code, qr_trackers, refresh_snapshot=True):
	"""Create one physical label for a Job/FG/subpart and link every process tracker."""
	if not qr_trackers:
		return None
	qr_trackers = sorted(
		qr_trackers,
		key=lambda tracker: tracker.process_name == "Packing",
	)

	fg = frappe.get_doc("Finished Good", finished_good)
	subpart = _find_subpart(fg, subpart_code)
	job_qty = float(_job_qty(job, finished_good) or 0)
	if subpart:
		subpart_name = subpart.get("subpart_name")
		ref_image = subpart.get("ref_image")
		qty_per_fg = float(subpart.get("qty_per_fg") or 1)
		uom = subpart.get("uom") or fg.get("default_uom")
	else:
		subpart_name = fg.fg_name
		ref_image = fg.get("fg_image")
		qty_per_fg = 1
		uom = fg.get("default_uom")

	total_qty = qty_per_fg * job_qty
	if total_qty <= 0:
		total_qty = max(float(qr.total_qty or 0) for qr in qr_trackers)

	label_key = make_label_key(job, finished_good, subpart_code)
	name = frappe.db.get_value(
		"Job Subpart Label",
		{"label_key": label_key},
		"name",
	)
	if not name:
		name = frappe.db.get_value(
			"Job Subpart Label",
			{"job": job, "finished_good": finished_good, "subpart_code": subpart_code},
			"name",
		)
	if name:
		doc = frappe.get_doc("Job Subpart Label", name)
		if not refresh_snapshot:
			return doc
		doc.subpart_name = subpart_name
		doc.ref_image = ref_image
		doc.qty_per_fg = qty_per_fg
		doc.job_qty = job_qty
		doc.total_qty = total_qty
		doc.uom = uom
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Job Subpart Label",
				"naming_series": "JSL-.YYYY.-",
				"job": job,
				"finished_good": finished_good,
				"subpart_code": subpart_code,
				"label_key": label_key,
				"subpart_name": subpart_name,
				"ref_image": ref_image,
				"qty_per_fg": qty_per_fg,
				"job_qty": job_qty,
				"total_qty": total_qty,
				"uom": uom,
				"qr_value": frappe.generate_hash(length=12).upper(),
			}
		)

	doc.set("processes", [])
	for tracker in qr_trackers:
		doc.append(
			"processes",
			{
				"process_name": tracker.process_name,
				"qr_code_master": tracker.name,
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	if not doc.qr_image:
		doc.scan_url = frappe.utils.get_url(f"/process-scan?part={doc.qr_value}")
		doc.qr_image = generate_qr_image(
			doc.qr_value,
			doc.scan_url,
			doc.doctype,
			doc.name,
		)
		doc.save(ignore_permissions=True)
	return doc


def sync_job_subpart_labels(job=None, refresh_existing=True):
	"""Backfill labels for existing process trackers and refresh uploaded diagrams."""
	filters = {"job": job} if job else None
	trackers = frappe.get_all(
		"QR Code Master",
		filters=filters,
		fields=[
			"name",
			"job",
			"finished_good",
			"subpart_code",
			"process_name",
			"total_qty",
			"creation",
		],
		order_by="creation asc",
		limit_page_length=0,
	)
	groups = {}
	for tracker in trackers:
		key = (tracker.job, tracker.finished_good, tracker.subpart_code)
		groups.setdefault(key, []).append(tracker)

	for (tracker_job, finished_good, subpart_code), rows in groups.items():
		create_or_update_label(
			tracker_job,
			finished_good,
			subpart_code,
			rows,
			refresh_snapshot=refresh_existing,
		)
	return len(groups)


def _tracker_has_activity(tracker):
	if float(tracker.completed_qty or 0) > 0:
		return True
	for doctype in ("QR Scan Log", "Department Transfer", "Packing Box Content", "Production Entry"):
		if frappe.db.exists(doctype, {"qr_code_master": tracker.name}):
			return True
	return False


def reconcile_job_subpart_trackers(job):
	"""Align generated trackers with subparts completed by the Data Entry team.

	Untouched placeholder trackers may be replaced. Once a tracker has scan,
	transfer, production, or packing activity, structural master changes are
	rejected so transaction history can never be relinked silently.
	"""
	from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import create_qr_master
	from elemental_erp.elemental_erp.doctype.qc_inspection.qc_inspection import (
		get_or_create_qc_inspection,
	)

	job_doc = frappe.get_doc("Job", job)
	expected = {}
	for fg_row in job_doc.fg_items:
		fg = frappe.get_doc("Finished Good", fg_row.finished_good)
		get_or_create_qc_inspection(job, fg_row.finished_good)
		if fg.subparts:
			for subpart in fg.subparts:
				expected[(fg.name, subpart.get("part_code"))] = {
					"processes": _process_names(subpart.get("processes")),
					"subpart_name": subpart.get("subpart_name"),
					"total_qty": float(subpart.get("qty_per_fg") or 1) * float(fg_row.job_qty or 0),
				}
		else:
			expected[(fg.name, fg.fg_code)] = {
				"processes": ["US Assembly"],
				"subpart_name": fg.fg_name,
				"total_qty": float(fg_row.job_qty or 0),
			}

	existing = frappe.get_all(
		"QR Code Master",
		filters={"job": job},
		fields=[
			"name",
			"job",
			"finished_good",
			"subpart_code",
			"subpart_name",
			"process_name",
			"total_qty",
			"completed_qty",
			"status",
			"creation",
		],
		order_by="creation asc",
		limit_page_length=0,
	)

	kept = {}
	obsolete = []
	for tracker in existing:
		identity = (tracker.finished_good, tracker.subpart_code)
		tracker_key = (*identity, tracker.process_name)
		definition = expected.get(identity)
		wrong_definition = (
			not definition
			or tracker.process_name not in definition["processes"]
			or abs(float(tracker.total_qty or 0) - definition["total_qty"]) > 1e-6
		)
		if wrong_definition or tracker_key in kept:
			obsolete.append(tracker)
		else:
			kept[tracker_key] = tracker

	active_obsolete = [tracker for tracker in obsolete if _tracker_has_activity(tracker)]
	if active_obsolete:
		details = ", ".join(
			f"{tracker.subpart_code}/{tracker.process_name}" for tracker in active_obsolete
		)
		frappe.throw(
			"Finished Good subparts/processes changed after production activity started. "
			f"Restore these tracker definitions or reverse their transactions first: {details}."
		)

	obsolete_names = {tracker.name for tracker in obsolete}
	for label_name in frappe.get_all(
		"Job Subpart Label",
		filters={"job": job},
		pluck="name",
		limit_page_length=0,
	):
		label = frappe.get_doc("Job Subpart Label", label_name)
		identity = (label.finished_good, label.subpart_code)
		if identity not in expected:
			if frappe.db.exists("Packing Box Content", {"job_subpart_label": label.name}):
				frappe.throw(
					f"Subpart label {label.name} is already packed and cannot be removed from the Job."
				)
			frappe.delete_doc("Job Subpart Label", label.name, ignore_permissions=True)
			continue
		remaining_rows = [
			row for row in label.processes if row.qr_code_master not in obsolete_names
		]
		if len(remaining_rows) != len(label.processes):
			label.set("processes", remaining_rows)
			label.save(ignore_permissions=True)

	for tracker in obsolete:
		frappe.delete_doc("QR Code Master", tracker.name, ignore_permissions=True)

	for (finished_good, subpart_code), definition in expected.items():
		trackers = []
		for process_name in definition["processes"]:
			tracker = kept.get((finished_good, subpart_code, process_name))
			if not tracker:
				tracker = create_qr_master(
					job=job,
					finished_good=finished_good,
					subpart_code=subpart_code,
					subpart_name=definition["subpart_name"],
					process_name=process_name,
					total_qty=definition["total_qty"],
				)
			trackers.append(tracker)
		create_or_update_label(job, finished_good, subpart_code, trackers)

	return len(expected)
