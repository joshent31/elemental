import frappe
from frappe.model.document import Document

TERMINAL_STATUSES = ("Closed", "Cancelled")


class Job(Document):
	def validate(self):
		self._block_edits_if_closed()

		is_new_job = self.is_new()

		for row in self.fg_items:
			if not row.added_on:
				row.added_on = frappe.utils.now_datetime()

		# generate QR / Design / QC trackers for any FG row that doesn't
		# have them yet — covers both the original items at Job creation
		# AND any FG the customer adds later, mid-Job. Idempotent: rows
		# already flagged trackers_generated are skipped every time.
		generate_trackers_for_new_fg_rows(self)

		# one Data Entry Task per Job (not per FG) — created once, on
		# whichever save first has fg_items, and left alone after that
		if self.fg_items:
			generate_data_entry_task_for_job(self)

		if is_new_job and self.status == "Draft":
			self.status = "Job Created"

	def _block_edits_if_closed(self):
		if self.is_new():
			return
		current_status = frappe.db.get_value("Job", self.name, "status")
		if current_status in TERMINAL_STATUSES:
			frappe.throw(
				f"This Job is {current_status} and cannot be modified. Use the \"Reopen Job\" "
				f"action (System Manager / Sales HOD only) if it genuinely needs to be reopened."
			)


def generate_trackers_for_new_fg_rows(doc):
	"""Runs on every save. For each Job FG Item row that hasn't had its
	trackers generated yet — new Job, or an FG the customer added
	mid-Job — creates that row's QR Code Master (part x process), Design
	Task, and QC Inspection, then marks the row done. Rows already
	processed are skipped, so this is safe to run on every single save."""
	from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import create_qr_master
	from elemental_erp.utils.qr_generator import generate_qr_image

	for fg_row in doc.fg_items:
		if fg_row.trackers_generated:
			continue

		fg = frappe.get_doc("Finished Good", fg_row.finished_good)

		# --- QR Code Master (part x process) ---
		if not fg.subparts:
			create_qr_master(
				job=doc.name, finished_good=fg.name,
				subpart_code=fg.fg_code, subpart_name=fg.fg_name,
				process_name="US Assembly", total_qty=fg_row.job_qty,
			)
		else:
			for sp in fg.subparts:
				raw = sp.processes or "US Assembly"
				processes = raw.split("\n") if "\n" in raw else raw.split(",")
				for process in [p.strip() for p in processes if p.strip()]:
					create_qr_master(
						job=doc.name, finished_good=fg.name,
						subpart_code=sp.part_code, subpart_name=sp.subpart_name,
						process_name=process, total_qty=(sp.qty_per_fg or 1) * fg_row.job_qty,
					)

		# --- Design Task (one per FG) ---
		if not frappe.db.exists("Design Task", {"job": doc.name, "finished_good": fg_row.finished_good}):
			task = frappe.get_doc({
				"doctype": "Design Task", "job": doc.name,
				"finished_good": fg_row.finished_good, "status": "Not Started",
			})
			task.qr_value = frappe.generate_hash(length=12).upper()
			task.insert(ignore_permissions=True)
			scan_url = frappe.utils.get_url(f"/design-scan?qr={task.qr_value}")
			task.qr_image = generate_qr_image(task.qr_value, scan_url, task.doctype, task.name)
			task.save(ignore_permissions=True)

		# --- QC Inspection (one per FG) ---
		if not frappe.db.exists("QC Inspection", {"job": doc.name, "finished_good": fg_row.finished_good}):
			insp = frappe.get_doc({
				"doctype": "QC Inspection", "job": doc.name,
				"finished_good": fg_row.finished_good, "status": "Pending",
			})
			insp.qr_value = frappe.generate_hash(length=12).upper()
			insp.insert(ignore_permissions=True)
			scan_url = frappe.utils.get_url(f"/qc-scan?qr={insp.qr_value}")
			insp.qr_image = generate_qr_image(insp.qr_value, scan_url, insp.doctype, insp.name)
			insp.save(ignore_permissions=True)

		fg_row.trackers_generated = 1


def generate_data_entry_task_for_job(doc):
	"""One Data Entry Task per Job (not per FG) — closes the loop between
	the uploaded diagram/BOQ Excel and the Finished Good / FG Subpart
	records actually being built. Idempotent regardless of how many times
	the Job is saved or how many FGs get added to it."""
	if frappe.db.exists("Data Entry Task", {"job": doc.name}):
		return
	frappe.get_doc({"doctype": "Data Entry Task", "job": doc.name, "status": "Pending"}).insert(
		ignore_permissions=True
	)


def cancel_related_records(job_name):
	"""Called from api.close_job / api.cancel_job — NOT a doctype hook
	anymore, since Job has no submit/cancel lifecycle. Cancels every
	submittable child record for this Job, and flips non-submittable
	trackers to a terminal status, so nothing is left looking "active"
	once the Job itself is closed or cancelled."""
	submittable_doctypes = [
		"Material Indent", "Material Issue", "Production Entry",
		"Packaging Entry", "Dispatch Entry", "Job Material Consumption",
	]
	for doctype in submittable_doctypes:
		names = frappe.get_all(doctype, {"job": job_name, "docstatus": 1}, pluck="name")
		for name in names:
			try:
				frappe.get_doc(doctype, name).cancel()
			except Exception:
				frappe.log_error(
					title=f"Job close/cancel cascade: could not cancel {doctype} {name}",
					message=frappe.get_traceback(),
				)

	status_doctypes = {
		"Design Task": ["Not Started", "In Progress"],
		"Data Entry Task": ["Pending", "In Progress"],
		"Packing Box": ["Label Created", "Packed"],
		"Department Transfer": ["Pending Dispatch", "In Transit"],
		"QC Inspection": ["Pending"],
	}
	for doctype, open_statuses in status_doctypes.items():
		frappe.db.sql(
			f"""UPDATE `tab{doctype}` SET status = 'Cancelled'
			    WHERE job = %s AND status IN ({", ".join(["%s"] * len(open_statuses))})""",
			[job_name, *open_statuses],
		)
