import frappe
from frappe.model.document import Document

TERMINAL_STATUSES = ("Closed", "Cancelled")


class Job(Document):
	def validate(self):
		self._block_edits_if_closed()
		self._validate_fg_rows()

		is_new_job = self.is_new()

		for row in self.fg_items:
			if not row.added_on:
				row.added_on = frappe.utils.now_datetime()

		if is_new_job and self.status == "Draft":
			self.status = "Job Created"

	def on_update(self):
		"""Generate trackers AFTER the document has its final name.

		validate() runs before naming_series resolves the docname,
		so inserting child docs there would link them to the temporary
		placeholder (new-job-xxxxx) instead of the real name.
		"""
		# generate QR / Design / QC trackers for any FG row that doesn't
		# have them yet — covers both the original items at Job creation
		# AND any FG the customer adds later, mid-Job. Idempotent: rows
		# already flagged trackers_generated are skipped every time.
		generate_trackers_for_new_fg_rows(self)

		# one Data Entry Task per Job (not per FG) — created once, on
		# whichever save first has fg_items, and left alone after that
		if self.fg_items:
			generate_data_entry_task_for_job(self)

	def before_print(self, print_settings=None):
		"""Ensure standard Print also sees subparts added after Job creation.

		The dedicated form action already prepares the traveller through the API,
		but users may select the format from Frappe's normal Print menu. Reconcile
		here as well so both entry points render the same Job-specific labels.
		"""
		if self.is_new():
			return
		from elemental_erp.elemental_erp.doctype.job_subpart_label.job_subpart_label import (
			reconcile_job_subpart_trackers,
		)

		reconcile_job_subpart_trackers(self.name)
		frappe.db.commit()

	def _block_edits_if_closed(self):
		if self.is_new():
			return
		current_status = frappe.db.get_value("Job", self.name, "status")
		if current_status in TERMINAL_STATUSES:
			frappe.throw(
				f"This Job is {current_status} and cannot be modified. Use the \"Reopen Job\" "
				f"action (System Manager / Sales HOD only) if it genuinely needs to be reopened."
			)

	def _validate_fg_rows(self):
		seen = set()
		for row in self.fg_items:
			if row.finished_good in seen:
				frappe.throw(
					f"Finished Good {row.finished_good} is listed more than once. "
					"Increase the quantity on the existing row instead."
				)
			seen.add(row.finished_good)
			if (row.job_qty or 0) <= 0:
				frappe.throw(f"Job Qty for {row.finished_good} must be greater than zero.")

			if row.name and row.trackers_generated:
				stored = frappe.db.get_value(
					"Job FG Item", row.name, ["finished_good", "job_qty"], as_dict=True
				)
				if stored and (
					stored.finished_good != row.finished_good
					or float(stored.job_qty or 0) != float(row.job_qty or 0)
				):
					frappe.throw(
						"Finished Good and Job Qty cannot be changed after trackers are generated "
						f"for row {row.idx}. Add a new Finished Good instead."
					)


def generate_trackers_for_new_fg_rows(doc):
	"""Runs on every save. For each Job FG Item row that hasn't had its
	trackers generated yet — new Job, or an FG the customer added
	mid-Job — creates that row's QR Code Master (part x process), Design
	Task, and QC Inspection, then marks the row done. Rows already
	processed are skipped, so this is safe to run on every single save."""
	from elemental_erp.elemental_erp.doctype.qr_code_master.qr_code_master import create_qr_master
	from elemental_erp.elemental_erp.doctype.job_subpart_label.job_subpart_label import (
		_process_names,
		create_or_update_label,
	)
	from elemental_erp.utils.qr_generator import generate_qr_image

	for fg_row in doc.fg_items:
		if fg_row.trackers_generated:
			continue

		fg = frappe.get_doc("Finished Good", fg_row.finished_good)

		# --- QR Code Master (part x process) ---
		if not fg.subparts:
			tracker = create_qr_master(
				job=doc.name, finished_good=fg.name,
				subpart_code=fg.fg_code, subpart_name=fg.fg_name,
				process_name="US Assembly", total_qty=fg_row.job_qty,
			)
			create_or_update_label(doc.name, fg.name, fg.fg_code, [tracker])
		else:
			for sp in fg.subparts:
				processes = _process_names(sp.get("processes"))
				trackers = []
				for process in processes:
					trackers.append(create_qr_master(
						job=doc.name, finished_good=fg.name,
						subpart_code=sp.get("part_code"), subpart_name=sp.get("subpart_name"),
						process_name=process, total_qty=(sp.get("qty_per_fg") or 1) * fg_row.job_qty,
					))
				create_or_update_label(doc.name, fg.name, sp.get("part_code"), trackers)

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
		# on_update runs after the parent database write; persist this flag or
		# the next Job save will generate the same trackers again.
		frappe.db.set_value(
			"Job FG Item", fg_row.name, "trackers_generated", 1, update_modified=False
		)


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
					title=f"Job cancel cascade: could not cancel {doctype} {name}",
					message=frappe.get_traceback(),
				)
				frappe.throw(
					f"Could not cancel linked {doctype} {name}. The Job was not cancelled; "
					"resolve the linked transaction first."
				)

	# Sales Invoices are ERPNext documents rather than custom child records,
	# but they are still part of the Job transaction chain.
	for invoice_name in frappe.get_all(
		"Sales Invoice", {"elemental_job": job_name, "docstatus": ["<", 2]}, pluck="name"
	):
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		if invoice.docstatus == 0:
			frappe.delete_doc("Sales Invoice", invoice.name, ignore_permissions=True)
		else:
			invoice.cancel()

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
