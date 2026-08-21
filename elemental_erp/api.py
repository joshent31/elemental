import frappe


@frappe.whitelist(allow_guest=True)
def get_qr_status(qr_value):
	"""Used by the public /qr/<qr_value> page to show current status."""
	qr = frappe.db.get_value(
		"QR Code Master",
		{"qr_value": qr_value},
		["name", "job", "finished_good", "subpart_code", "subpart_name", "process_name", "total_qty", "completed_qty", "status"],
		as_dict=True,
	)
	if not qr:
		frappe.throw("Invalid QR code", frappe.DoesNotExistError)
	return qr


@frappe.whitelist()
def scan_qr(qr_value, department=None, qty_scanned=1, remarks=None):
	"""Called when a floor operator scans a part's QR code at a process
	station. Requires login (department users). Creates a QR Scan Log,
	which in turn advances the QR Code Master status via doc_events."""
	qr_name = frappe.db.get_value("QR Code Master", {"qr_value": qr_value}, "name")
	if not qr_name:
		frappe.throw("Invalid QR code")

	log = frappe.get_doc(
		{
			"doctype": "QR Scan Log",
			"qr_code_master": qr_name,
			"department": department,
			"qty_scanned": float(qty_scanned),
			"remarks": remarks,
		}
	)
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	return frappe.get_doc("QR Code Master", qr_name).as_dict()


# ---------------------------------------------------------------------------
# Inter-department transfer: sending dept scans the PART qr, creates a
# Department Transfer with its OWN qr (printed on the transfer slip that
# travels with the box); receiving dept scans that TRANSFER qr and confirms
# qty received.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def lookup_part_qr(qr_value):
	"""Used by the /transfer-out screen right after a camera scan, to show
	the operator what part/job they just scanned before they enter qty."""
	qr = frappe.db.get_value(
		"QR Code Master",
		{"qr_value": qr_value},
		["name", "job", "finished_good", "subpart_code", "subpart_name", "process_name",
		 "total_qty", "completed_qty", "status"],
		as_dict=True,
	)
	if not qr:
		frappe.throw("Part QR not recognised")
	return qr


@frappe.whitelist()
def create_transfer(qr_value, from_department, to_department, transfer_qty, remarks=None):
	"""Sending department: scanned the part QR, entered qty + destination
	dept. Creates the Department Transfer doc and renders its own QR (a
	different code from the part's QR) to print on the physical slip."""
	from elemental_erp.utils.qr_generator import generate_qr_image

	qr_master_name = frappe.db.get_value("QR Code Master", {"qr_value": qr_value}, "name")
	if not qr_master_name:
		frappe.throw("Part QR not recognised")

	qr_master = frappe.get_doc("QR Code Master", qr_master_name)

	doc = frappe.get_doc(
		{
			"doctype": "Department Transfer",
			"job": qr_master.job,
			"qr_code_master": qr_master_name,
			"from_department": from_department,
			"to_department": to_department,
			"transfer_qty": float(transfer_qty),
			"status": "In Transit",
			"dispatched_by": frappe.session.user,
			"dispatched_on": frappe.utils.now_datetime(),
			"remarks": remarks,
		}
	)
	doc.transfer_qr_value = frappe.generate_hash(length=12).upper()
	doc.insert(ignore_permissions=True)

	scan_url = frappe.utils.get_url(f"/transfer-in?qr={doc.transfer_qr_value}")
	file_url = generate_qr_image(doc.transfer_qr_value, scan_url, doc.doctype, doc.name)
	doc.transfer_qr_image = file_url
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"transfer_name": doc.name,
		"transfer_qr_value": doc.transfer_qr_value,
		"print_url": frappe.utils.get_url(
			f"/printview?doctype=Department%20Transfer&name={doc.name}&format=Department Transfer Slip&no_letterhead=0"
		),
	}


@frappe.whitelist(allow_guest=True)
def get_transfer(transfer_qr_value):
	"""Used by the /transfer-in screen to show what's expected before the
	receiving operator confirms qty."""
	transfer = frappe.db.get_value(
		"Department Transfer",
		{"transfer_qr_value": transfer_qr_value},
		["name", "job", "qr_code_master", "subpart_label", "from_department",
		 "to_department", "transfer_qty", "status"],
		as_dict=True,
	)
	if not transfer:
		frappe.throw("Transfer QR not recognised", frappe.DoesNotExistError)
	return transfer


@frappe.whitelist()
def receive_transfer(transfer_qr_value, received_qty, remarks=None):
	"""Receiving department: scanned the TRANSFER slip's QR, enters the qty
	actually received. Flags a mismatch if it doesn't match qty sent, and
	logs a QR Scan Log against the original part QR so QR Code Master
	progress reflects material that has actually landed in the next dept."""
	transfer_name = frappe.db.get_value(
		"Department Transfer", {"transfer_qr_value": transfer_qr_value}, "name"
	)
	if not transfer_name:
		frappe.throw("Transfer QR not recognised")

	doc = frappe.get_doc("Department Transfer", transfer_name)
	if doc.status == "Received":
		frappe.throw("This transfer has already been received")

	doc.received_qty = float(received_qty)
	doc.compute_diff()
	doc.status = "Received" if doc.qty_diff == 0 else "Qty Mismatch"
	doc.received_by = frappe.session.user
	doc.received_on = frappe.utils.now_datetime()
	if remarks:
		doc.remarks = (doc.remarks or "") + f"\n[Receive] {remarks}"
	doc.save(ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "QR Scan Log",
			"qr_code_master": doc.qr_code_master,
			"department": doc.to_department,
			"qty_scanned": 0,  # inter-dept receipt doesn't add production progress by itself
			"remarks": f"Received {doc.received_qty} of {doc.transfer_qty} via Department Transfer {doc.name}"
			+ (" — QTY MISMATCH" if doc.status == "Qty Mismatch" else ""),
		}
	).insert(ignore_permissions=True)

	# roll the received qty into a running total for (Job, To-Department) —
	# this is what "Close Department" checks against before closing.
	from elemental_erp.elemental_erp.doctype.job_department_status.job_department_status import (
		get_or_create,
	)

	dept_status = get_or_create(doc.job, doc.to_department)
	dept_status.total_qty_received = (dept_status.total_qty_received or 0) + doc.received_qty
	dept_status.save(ignore_permissions=True)

	frappe.db.commit()

	return doc.as_dict()


@frappe.whitelist()
def get_department_job_summary(job, department):
	"""Used by /transfer-in to show the receiving operator a running total
	for their department on this Job, and whether it's already closed —
	before they decide to close it out."""
	from elemental_erp.elemental_erp.doctype.job_department_status.job_department_status import (
		get_or_create,
	)

	dept_status = get_or_create(job, department)
	pending_transfers = frappe.db.count(
		"Department Transfer",
		{"job": job, "to_department": department, "status": ["!=", "Received"]},
	)
	return {
		"status": dept_status.status,
		"total_qty_received": dept_status.total_qty_received,
		"pending_transfers": pending_transfers,
	}


@frappe.whitelist()
def close_department(job, department, remarks=None):
	"""Explicit action: receiving department confirms they have everything
	they expect for this Job and closes their portion of the work.
	Refuses to close if there are still transfers in transit / mismatched,
	so it can't be closed out from under an incomplete handoff."""
	from elemental_erp.elemental_erp.doctype.job_department_status.job_department_status import (
		get_or_create,
	)

	open_issues = frappe.db.count(
		"Department Transfer",
		{"job": job, "to_department": department, "status": ["in", ["Pending Dispatch", "In Transit", "Qty Mismatch"]]},
	)
	if open_issues:
		frappe.throw(
			f"Cannot close {department} for {job}: {open_issues} transfer(s) still pending or mismatched."
		)

	dept_status = get_or_create(job, department)
	dept_status.status = "Closed"
	dept_status.closed_by = frappe.session.user
	dept_status.closed_on = frappe.utils.now_datetime()
	if remarks:
		dept_status.remarks = remarks
	dept_status.save(ignore_permissions=True)
	frappe.db.commit()
	return dept_status.as_dict()


# ---------------------------------------------------------------------------
# Material Issue -> Job Material Consumption
#
# Material issued to a department against a Job sits as WIP ("Issued") and is
# NOT booked as consumed. Only once Packaging confirms the whole Job/FG is
# fully packed does the system roll up every department's Material Issue for
# that Job into ONE Job Material Consumption draft — costing then books the
# ACTUAL qty used (which may be less than what was issued), not the full
# indent/issue qty.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def mark_job_packaging_completed(job):
	"""Called by Packaging once every FG on the Job is packed. Flips the
	Job flag, and generates the (Draft) Job Material Consumption doc for
	costing to review — this is the single point where "all items need to
	consume at once" happens."""
	from elemental_erp.elemental_erp.doctype.job_material_consumption.job_material_consumption import (
		generate_for_job,
	)

	job_doc = frappe.get_doc("Job", job)
	if job_doc.packaging_completed:
		frappe.throw("Packaging is already marked completed for this Job.")

	job_doc.packaging_completed = 1
	job_doc.packaging_completed_on = frappe.utils.now_datetime()
	job_doc.status = "Material Consumption Pending"
	job_doc.save(ignore_permissions=True)

	consumption = generate_for_job(job)
	frappe.db.commit()
	return {"job": job, "job_material_consumption": consumption.name}


# ---------------------------------------------------------------------------
# Packing labels / box mapping
#
# Packaging creates N box labels for a Job (e.g. 20), each with its own QR.
# As parts/FGs are physically packed, their part-QR is scanned and mapped
# into a specific box — so each box's contents are known before it ships.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_packing_labels(job, total_boxes):
	"""Generates `total_boxes` Packing Box records (Box 1 of N ... Box N of N),
	each with a unique QR image, ready to print and stick on the boxes."""
	from elemental_erp.utils.qr_generator import generate_qr_image

	total_boxes = int(total_boxes)
	if total_boxes <= 0:
		frappe.throw("Total boxes must be a positive number")

	frappe.db.set_value("Job", job, "total_packing_boxes", total_boxes)

	created = []
	for box_no in range(1, total_boxes + 1):
		box = frappe.get_doc(
			{
				"doctype": "Packing Box",
				"job": job,
				"box_no": box_no,
				"total_boxes": total_boxes,
				"status": "Label Created",
			}
		)
		box.box_qr_value = frappe.generate_hash(length=12).upper()
		box.insert(ignore_permissions=True)

		scan_url = frappe.utils.get_url(f"/pack-box?box={box.box_qr_value}")
		file_url = generate_qr_image(box.box_qr_value, scan_url, box.doctype, box.name)
		box.box_qr_image = file_url
		box.save(ignore_permissions=True)
		created.append(box.name)

	frappe.db.commit()
	return {"created": len(created), "box_names": created}


@frappe.whitelist(allow_guest=True)
def lookup_box(box_qr_value):
	box = frappe.db.get_value(
		"Packing Box",
		{"box_qr_value": box_qr_value},
		["name", "job", "box_no", "total_boxes", "status", "dispatch_entry"],
		as_dict=True,
	)
	if not box:
		frappe.throw("Box QR not recognised", frappe.DoesNotExistError)
	box["contents"] = frappe.get_all(
		"Packing Box Content",
		filters={"parent": box["name"]},
		fields=["subpart_label", "packed_qty"],
	)
	return box


@frappe.whitelist()
def map_part_to_box(box_qr_value, part_qr_value, qty):
	"""Packing operator: scan the BOX QR, then scan a PART QR, enter qty —
	maps that part into this box's contents list. Blocked until QC has
	Passed the part's Finished Good."""
	box_name = frappe.db.get_value("Packing Box", {"box_qr_value": box_qr_value}, "name")
	if not box_name:
		frappe.throw("Box QR not recognised")
	qr_master = frappe.db.get_value(
		"QR Code Master", {"qr_value": part_qr_value}, ["name", "job", "finished_good"], as_dict=True
	)
	if not qr_master:
		frappe.throw("Part QR not recognised")

	from elemental_erp.elemental_erp.doctype.qc_inspection.qc_inspection import qc_passed

	if qr_master.finished_good and not qc_passed(qr_master.job, qr_master.finished_good):
		frappe.throw(
			f"QC Inspection has not Passed yet for {qr_master.finished_good} on this Job \u2014 "
			f"this part cannot be packed until QC scans it Passed (see /qc-scan)."
		)

	box = frappe.get_doc("Packing Box", box_name)
	box.append("contents", {
		"qr_code_master": qr_master.name,
		"packed_qty": float(qty),
		"scanned_on": frappe.utils.now_datetime(),
	})
	if box.status == "Label Created":
		box.status = "Packed"
	box.save(ignore_permissions=True)
	frappe.db.commit()
	return box.as_dict()


# ---------------------------------------------------------------------------
# Dispatch scan (loading the vehicle) and post-dispatch site scan
# (received at site / installed)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_or_create_dispatch_entry(job, vehicle_no=None):
	existing = frappe.db.get_value(
		"Dispatch Entry", {"job": job, "dispatch_status": "Scheduled"}, "name"
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Dispatch Entry",
			"job": job,
			"vehicle_no": vehicle_no,
			"dispatch_status": "Scheduled",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def get_job_box_progress(job):
	"""Used by /dispatch-scan to show, at any moment: how many boxes are
	packed (contents mapped) vs how many have actually been scanned onto
	the vehicle vs the total \u2014 the "how many packaging was done and how
	much till scanned" view."""
	total = frappe.db.get_value("Job", job, "total_packing_boxes") or frappe.db.count("Packing Box", {"job": job})
	packed = frappe.db.count(
		"Packing Box",
		{"job": job, "status": ["in", ["Packed", "Dispatched", "Received at Site", "Installed"]]},
	)
	dispatched = frappe.db.count(
		"Packing Box", {"job": job, "status": ["in", ["Dispatched", "Received at Site", "Installed"]]}
	)
	return {"job": job, "total": total, "packed": packed, "dispatched": dispatched}


@frappe.whitelist()
def scan_box_dispatch(box_qr_value, dispatch_entry):
	"""Scan each box's QR as it's loaded onto the vehicle. Shows a running
	'X of N boxes loaded' count for the Job from the caller side. The
	moment every box is loaded, a Draft Sales Invoice is created
	automatically — invoicing is never possible before this point (see
	create_sales_invoice_for_job)."""
	box_name = frappe.db.get_value("Packing Box", {"box_qr_value": box_qr_value}, "name")
	if not box_name:
		frappe.throw("Box QR not recognised")

	box = frappe.get_doc("Packing Box", box_name)
	if box.status == "Dispatched":
		frappe.throw(f"Box {box.box_no} is already marked dispatched.")

	box.status = "Dispatched"
	box.dispatch_entry = dispatch_entry
	box.dispatched_on = frappe.utils.now_datetime()
	box.save(ignore_permissions=True)

	progress = get_job_box_progress(box.job)
	loaded, total = progress["dispatched"], progress["total"]

	sales_invoice = None
	if total and loaded >= total:
		try:
			result = create_sales_invoice_for_job(box.job)
			sales_invoice = result.get("sales_invoice")
		except Exception:
			frappe.log_error(
				title=f"Auto Sales Invoice creation failed for Job {box.job}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()
	return {
		"box_no": box.box_no, "job": box.job,
		"loaded": loaded, "total": total, "packed": progress["packed"],
		"sales_invoice": sales_invoice,
	}


@frappe.whitelist(allow_guest=True)
def scan_box_received(box_qr_value, received_by=None):
	"""Site scan: box has arrived and been received at the installation site."""
	box_name = frappe.db.get_value("Packing Box", {"box_qr_value": box_qr_value}, "name")
	if not box_name:
		frappe.throw("Box QR not recognised")
	box = frappe.get_doc("Packing Box", box_name)
	box.status = "Received at Site"
	box.received_at_site_on = frappe.utils.now_datetime()
	box.received_by = received_by or frappe.session.user
	box.save(ignore_permissions=True)
	frappe.db.commit()
	return box.as_dict()


@frappe.whitelist(allow_guest=True)
def scan_box_installed(box_qr_value, installed_by=None):
	"""Site scan: confirms installation actually happened for this box's contents."""
	box_name = frappe.db.get_value("Packing Box", {"box_qr_value": box_qr_value}, "name")
	if not box_name:
		frappe.throw("Box QR not recognised")
	box = frappe.get_doc("Packing Box", box_name)
	box.status = "Installed"
	box.installed_on = frappe.utils.now_datetime()
	box.installed_by = installed_by or frappe.session.user
	box.save(ignore_permissions=True)

	remaining = frappe.db.count("Packing Box", {"job": box.job, "status": ["!=", "Installed"]})
	if remaining == 0:
		frappe.db.set_value("Job", box.job, "status", "Installed")
	frappe.db.commit()
	return box.as_dict()


# ---------------------------------------------------------------------------
# BOM-driven Material Indent + auto Purchase Order from shortfall
# ---------------------------------------------------------------------------

@frappe.whitelist()
def generate_indent_items_from_bom(job):
	"""Aggregates each not-yet-indented Finished Good's BOM (FG BOM Item) on
	this Job, multiplied by its Job Qty, into one raw-material list — so
	Costing doesn't have to type the recipe from memory. Only covers FG
	rows where indent_raised is still 0, so calling this again after the
	customer adds a new FG only pulls the NEW item's requirement, not a
	re-total of everything already indented."""
	job_doc = frappe.get_doc("Job", job)
	totals = {}
	covered_fgs = []
	for fg_row in job_doc.fg_items:
		if fg_row.indent_raised:
			continue
		fg = frappe.get_doc("Finished Good", fg_row.finished_good)
		if fg.bom_items:
			covered_fgs.append(fg_row.finished_good)
		for bom_row in fg.bom_items:
			qty = (bom_row.qty_per_fg or 0) * (fg_row.job_qty or 0)
			key = bom_row.raw_material
			if key not in totals:
				totals[key] = {"raw_material": key, "uom": bom_row.uom, "required_qty": 0}
			totals[key]["required_qty"] += qty

	if not totals:
		frappe.throw(
			"No un-indented Finished Goods with a BOM found on this Job — either "
			"everything's already been indented, or the BOM (Raw Material BOM "
			"section) hasn't been filled in on the relevant Finished Good yet."
		)
	return {"items": list(totals.values()), "covered_finished_goods": covered_fgs}


def _default_company():
	"""Best-effort default company for auto-created ERPNext documents
	(Purchase Order, Sales Invoice) — falls back to the first Company in the
	system if the user has no default set. Still a DRAFT either way, so a
	human confirms/corrects it before submitting."""
	company = frappe.defaults.get_user_default("company")
	if company:
		return company
	return frappe.db.get_value("Company", {}, "name", order_by="creation asc")


def _resolve_supplier(supplier):
	"""Accepts either an existing Supplier name, or a new vendor name to
	create on the fly — 'existing supplier or any new vendor' per the
	client's requirement."""
	if not supplier:
		return None
	if frappe.db.exists("Supplier", supplier):
		return supplier
	new_supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier,
			"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
			"supplier_type": "Company",
		}
	)
	new_supplier.insert(ignore_permissions=True, ignore_mandatory=True)
	return new_supplier.name


def _create_po_from_indent_doc(indent, supplier=None):
	"""Core logic shared by the manual API call and the automatic creation
	that fires the moment a Material Indent is approved (submitted). Takes
	the already-validated in-memory indent doc, since its shortfall_qty
	values were just computed in validate(). Returns None if there's no
	shortfall to buy."""
	shortfall_rows = [row for row in indent.items if (row.shortfall_qty or 0) > 0]
	if not shortfall_rows:
		return None

	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": _default_company(),
			"supplier": _resolve_supplier(supplier),
			"transaction_date": frappe.utils.nowdate(),
			"schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
			"items": [
				{
					"item_code": row.raw_material,
					"qty": row.shortfall_qty,
					"uom": row.uom,
					"schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
				}
				for row in shortfall_rows
			],
		}
	)
	po.insert(ignore_permissions=True, ignore_mandatory=True)
	indent.db_set("purchase_order", po.name)
	return po


@frappe.whitelist()
def create_purchase_order_from_indent(material_indent, supplier=None):
	"""Manual fallback / re-trigger — e.g. to attach a supplier after the
	automatic Draft PO (created on Indent approval) was left blank.
	`supplier` can be an existing Supplier name or a brand new vendor name."""
	indent = frappe.get_doc("Material Indent", material_indent)
	if indent.docstatus != 1:
		frappe.throw("Material Indent must be submitted (Approved) first.")
	if indent.purchase_order:
		frappe.throw(f"Purchase Order {indent.purchase_order} already exists for this Indent.")

	po = _create_po_from_indent_doc(indent, supplier)
	if not po:
		frappe.throw("No shortfall on this Indent — nothing to purchase.")
	frappe.db.commit()
	return {"purchase_order": po.name}


# ---------------------------------------------------------------------------
# QC: must Pass before Packaging is allowed. No rework/return workflow —
# a Fail just sits there, and re-scanning the same QR overwrites the result
# once the issue is corrected on the floor.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def lookup_qc_inspection(qr_value):
	insp = frappe.db.get_value(
		"QC Inspection",
		{"qr_value": qr_value},
		["name", "job", "finished_good", "status", "inspector", "inspected_on", "remarks"],
		as_dict=True,
	)
	if not insp:
		frappe.throw("QC QR not recognised", frappe.DoesNotExistError)
	return insp


@frappe.whitelist()
def record_qc_result(qr_value, result, inspector=None, remarks=None):
	"""result is 'Pass' or 'Fail'. Overwrites this QC Inspection's status —
	there's no separate rework/reinspection doctype, QC just re-scans once
	the issue is fixed."""
	name = frappe.db.get_value("QC Inspection", {"qr_value": qr_value}, "name")
	if not name:
		frappe.throw("QC QR not recognised")
	if result not in ("Pass", "Fail"):
		frappe.throw("Result must be 'Pass' or 'Fail'")

	insp = frappe.get_doc("QC Inspection", name)
	insp.status = "Passed" if result == "Pass" else "Failed"
	insp.inspector = inspector
	insp.inspected_on = frappe.utils.now_datetime()
	if remarks:
		insp.remarks = remarks
	insp.save(ignore_permissions=True)
	frappe.db.commit()
	return insp.as_dict()


# ---------------------------------------------------------------------------
# Design: scan the Job/FG's Design Task QR to start/stop the drawing work,
# time and cost calculated from the gap between the two scans.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def lookup_design_task(qr_value):
	task = frappe.db.get_value(
		"Design Task",
		{"qr_value": qr_value},
		["name", "job", "finished_good", "status", "assigned_designer", "start_time", "end_time", "hours_spent", "design_cost"],
		as_dict=True,
	)
	if not task:
		frappe.throw("Design QR not recognised", frappe.DoesNotExistError)
	return task


@frappe.whitelist()
def start_design(qr_value, designer=None):
	name = frappe.db.get_value("Design Task", {"qr_value": qr_value}, "name")
	if not name:
		frappe.throw("Design QR not recognised")
	task = frappe.get_doc("Design Task", name)
	if task.status == "In Progress":
		frappe.throw("This design task is already in progress.")
	task.status = "In Progress"
	task.start_time = frappe.utils.now_datetime()
	if designer:
		task.assigned_designer = designer
	task.save(ignore_permissions=True)
	frappe.db.commit()
	return task.as_dict()


@frappe.whitelist()
def complete_design(qr_value):
	name = frappe.db.get_value("Design Task", {"qr_value": qr_value}, "name")
	if not name:
		frappe.throw("Design QR not recognised")
	task = frappe.get_doc("Design Task", name)
	if not task.start_time:
		frappe.throw("This design task was never started — scan Start first.")
	task.status = "Completed"
	task.end_time = frappe.utils.now_datetime()
	task.compute_time_and_cost()
	task.save(ignore_permissions=True)
	frappe.db.commit()
	return task.as_dict()


# ---------------------------------------------------------------------------
# Data Entry: closes the loop between the uploaded diagram/BOQ Excel and the
# Finished Good / FG Subpart records actually existing in the system.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def complete_data_entry_task(job, hours_spent=None, remarks=None):
	name = frappe.db.get_value("Data Entry Task", {"job": job}, "name")
	if not name:
		frappe.throw("No Data Entry Task found for this Job.")
	task = frappe.get_doc("Data Entry Task", name)
	task.status = "Completed"
	task.fg_records_created = 1
	task.completed_on = frappe.utils.now_datetime()
	if hours_spent:
		task.hours_spent = float(hours_spent)
	if remarks:
		task.remarks = remarks
	task.save(ignore_permissions=True)
	frappe.db.commit()
	return task.as_dict()


# ---------------------------------------------------------------------------
# Sales Invoice against the Job (draft — Sales/Accounts still need to review
# rates, taxes, etc. before submitting)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_sales_invoice_for_job(job):
	"""Only allowed once the loading scan is fully complete — i.e. every
	Packing Box for this Job has been scanned onto the vehicle. This is
	both called automatically the moment the last box is scanned (see
	scan_box_dispatch) and available as a manual fallback, but either way
	this same check applies so it can never fire early."""
	total_boxes = frappe.db.count("Packing Box", {"job": job})
	if total_boxes:
		not_yet_loaded = frappe.db.count(
			"Packing Box", {"job": job, "status": ["not in", ["Dispatched", "Received at Site", "Installed"]]}
		)
		if not_yet_loaded:
			frappe.throw(
				f"Cannot create a Sales Invoice yet — {not_yet_loaded} of {total_boxes} box(es) "
				f"have not been scanned as loaded/dispatched."
			)

	if frappe.db.exists("Sales Invoice", {"elemental_job": job}):
		frappe.throw("A Sales Invoice already exists for this Job.")

	job_doc = frappe.get_doc("Job", job)
	items = []
	skipped = []
	for fg_row in job_doc.fg_items:
		erpnext_item = frappe.db.get_value("Finished Good", fg_row.finished_good, "erpnext_item")
		if not erpnext_item:
			skipped.append(fg_row.finished_good)
			continue
		items.append({"item_code": erpnext_item, "qty": fg_row.job_qty})

	if not items:
		frappe.throw(
			"None of the Finished Goods on this Job are mapped to an ERPNext Item "
			"(Finished Good \u2192 Linked ERPNext Item) — map at least one before invoicing."
		)

	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": job_doc.customer,
			"company": _default_company(),
			"elemental_job": job_doc.name,
			"items": items,
		}
	)
	si.insert(ignore_permissions=True, ignore_mandatory=True)
	frappe.db.commit()
	return {"sales_invoice": si.name, "skipped_fgs": skipped}


# ---------------------------------------------------------------------------
# Explicit final confirmation that the Job is complete — deliberately a
# separate action from "last box installed" so a person signs off on it
# rather than it being purely inferred.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def confirm_job_installation_complete(job, confirmed_by=None):
	remaining = frappe.db.count("Packing Box", {"job": job, "status": ["!=", "Installed"]})
	if remaining:
		frappe.throw(f"{remaining} box(es) are not yet marked Installed — cannot close the Job.")
	frappe.db.set_value("Job", job, "status", "Closed")
	any_qr = frappe.db.get_value("QR Code Master", {"job": job}, "name")
	if any_qr:
		frappe.get_doc(
			{
				"doctype": "QR Scan Log",
				"qr_code_master": any_qr,
				"department": "Installation",
				"qty_scanned": 0,
				"remarks": f"Job confirmed fully installed and closed by {confirmed_by or frappe.session.user}",
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	return {"job": job, "status": "Closed"}


# ---------------------------------------------------------------------------
# Employee gate check-in / check-out — scan the Employee's own QR (printed
# on their ID badge, auto-generated when the Employee record was created).
# Automatically alternates IN/OUT based on their last scan, logs an
# Employee Checkin, and rebuilds today's Attendance from the day's scans.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def lookup_employee_qr(qr_value):
	"""Used by /gate-scan right after a scan, to show who it is and what
	the next action will be, before actually logging it."""
	employee = frappe.db.get_value(
		"Employee",
		{"employee_qr_value": qr_value},
		["name", "employee_name", "department", "designation"],
		as_dict=True,
	)
	if not employee:
		frappe.throw("Employee QR not recognised", frappe.DoesNotExistError)

	last_log_type = frappe.db.get_value(
		"Employee Checkin", {"employee": employee.name}, "log_type", order_by="time desc"
	)
	employee["next_action"] = "OUT" if last_log_type == "IN" else "IN"
	return employee


@frappe.whitelist(allow_guest=True)
def gate_scan(qr_value):
	"""The actual gate scan: figures out IN vs OUT from the employee's last
	checkin (no manual toggle needed), logs an Employee Checkin, and \u2014 on
	an OUT scan \u2014 rebuilds today's Attendance from the day's checkins.

	Server-side duplicate guard: a badge held up to a continuously-running
	camera (see /gate-scan) gets seen across many video frames, and the
	page's own debounce is only a client-side safeguard \u2014 if it's ever
	bypassed (a second gate device, a client bug, a slow network retry),
	this refuses to log a second checkin for the same employee within a
	short window and just returns the existing one instead."""
	employee = frappe.db.get_value(
		"Employee", {"employee_qr_value": qr_value}, ["name", "employee_name"], as_dict=True
	)
	if not employee:
		frappe.throw("Employee QR not recognised")

	last_checkin = frappe.db.get_value(
		"Employee Checkin", {"employee": employee.name},
		["name", "log_type", "time"], order_by="time desc", as_dict=True,
	)

	DUPLICATE_GUARD_SECONDS = 15
	if last_checkin and (frappe.utils.now_datetime() - last_checkin.time).total_seconds() < DUPLICATE_GUARD_SECONDS:
		return {
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"log_type": last_checkin.log_type,
			"time": last_checkin.time,
			"attendance": None,
			"duplicate_ignored": True,
		}

	log_type = "OUT" if last_checkin and last_checkin.log_type == "IN" else "IN"

	checkin = frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": employee.name,
			"log_type": log_type,
			"time": frappe.utils.now_datetime(),
		}
	)
	checkin.insert(ignore_permissions=True)

	attendance_name = None
	if log_type == "OUT":
		from elemental_erp.employee_gate import upsert_attendance_for_day

		attendance_name = upsert_attendance_for_day(employee.name, frappe.utils.nowdate())

	frappe.db.commit()
	return {
		"employee": employee.name,
		"employee_name": employee.employee_name,
		"log_type": log_type,
		"time": checkin.time,
		"attendance": attendance_name,
	}


# ---------------------------------------------------------------------------
# Quotation -> Job. Production can start the moment the customer approves
# the quotation by email/call — the formal PO is logged on the Job later,
# whenever it actually arrives, without blocking anything in between.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def mark_quotation_approved(quotation, approval_reference=None):
	"""Records the customer's approval (an email thread, a call note —
	whatever it actually was) WITHOUT waiting for a formal PO. This is
	what unlocks "Create Job from Quotation"."""
	q = frappe.get_doc("Elemental Quotation", quotation)
	if q.docstatus != 1:
		frappe.throw("Quotation must be submitted (Sent to Customer) first.")
	q.status = "Approved by Customer"
	q.approval_reference = approval_reference
	q.approved_on = frappe.utils.now_datetime()
	q.approved_by = frappe.session.user
	q.save(ignore_permissions=True)
	frappe.db.commit()
	return q.as_dict()


@frappe.whitelist()
def create_job_from_quotation(quotation):
	"""Creates a Job from an Approved quotation, carrying over customer,
	brand, and every quoted Finished Good as a Job FG Item. The Job's own
	tracker-generation (QR / Design / QC) then fires normally on save,
	same as any other Job — this just seeds the FG list instead of
	someone re-typing it."""
	q = frappe.get_doc("Elemental Quotation", quotation)
	if q.status != "Approved by Customer":
		frappe.throw("Quotation must be marked Approved by Customer before creating a Job from it.")
	if q.job:
		frappe.throw(f"Job {q.job} already exists for this Quotation.")

	job = frappe.get_doc(
		{
			"doctype": "Job",
			"job_name": f"Job for {q.name}",
			"customer": q.customer,
			"brand": q.brand,
			"quotation": q.name,
			"fg_items": [
				{"finished_good": row.finished_good, "job_qty": row.qty}
				for row in q.items
			],
		}
	)
	job.insert(ignore_permissions=True)

	q.status = "Converted to Job"
	q.job = job.name
	q.save(ignore_permissions=True)
	frappe.db.commit()
	return {"job": job.name}


# ---------------------------------------------------------------------------
# Job close / reopen / cancel — Job has no submit/cancel lifecycle anymore
# (it stays open so new Finished Goods can keep being added), so "Closed"
# and "Cancelled" are enforced by Job.validate() blocking further edits once
# status reaches either. Three distinct actions, not to be confused:
#   - close_job: administrative "mark this Closed now" for edge cases that
#     don't go through the box-by-box confirm_job_installation_complete
#     flow. Does NOT cancel anything — the work was legitimately completed.
#   - cancel_job: voids a Job that's being abandoned before completion
#     (customer cancelled the order, etc.) — THIS cascades cancel to every
#     submittable child record, unlike close_job.
#   - reopen_job: the only sanctioned way back out of Closed/Cancelled.
# All three write directly via frappe.db.set_value, bypassing validate(),
# rather than fighting the lock they're specifically allowed to cross.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def close_job(job):
	"""Administrative close — does NOT cancel any related records, since
	the work here was completed legitimately. For the normal path where
	every box has been installed, prefer confirm_job_installation_complete
	instead, which checks that before closing; this is the manual
	fallback for Jobs that don't go through packing boxes at all."""
	if "System Manager" not in frappe.get_roles() and "Elemental Sales HOD" not in frappe.get_roles():
		frappe.throw("Only a System Manager or Sales HOD can close a Job this way.")

	current_status = frappe.db.get_value("Job", job, "status")
	if current_status in ("Closed", "Cancelled"):
		frappe.throw(f"This Job is already {current_status}.")

	frappe.db.set_value("Job", job, "status", "Closed")
	frappe.db.commit()
	return {"job": job, "status": "Closed"}


@frappe.whitelist()
def cancel_job(job, reason=None):
	"""Voids a Job that's being abandoned before completion — cascades
	cancel to every submittable child record and flips non-submittable
	trackers to Cancelled, unlike close_job."""
	from elemental_erp.elemental_erp.doctype.job.job import cancel_related_records

	if "System Manager" not in frappe.get_roles() and "Elemental Sales HOD" not in frappe.get_roles():
		frappe.throw("Only a System Manager or Sales HOD can cancel a Job.")

	current_status = frappe.db.get_value("Job", job, "status")
	if current_status in ("Closed", "Cancelled"):
		frappe.throw(f"This Job is already {current_status}.")

	cancel_related_records(job)
	frappe.db.set_value("Job", job, "status", "Cancelled")
	if reason:
		frappe.db.set_value("Job", job, "remarks", f"Cancelled: {reason}")
	frappe.db.commit()
	return {"job": job, "status": "Cancelled"}


@frappe.whitelist()
def reopen_job(job, new_status="Job Created"):
	if "System Manager" not in frappe.get_roles() and "Elemental Sales HOD" not in frappe.get_roles():
		frappe.throw("Only a System Manager or Sales HOD can reopen a Closed/Cancelled Job.")

	current_status = frappe.db.get_value("Job", job, "status")
	if current_status not in ("Closed", "Cancelled"):
		frappe.throw("This Job isn't Closed or Cancelled — nothing to reopen.")

	frappe.db.set_value("Job", job, "status", new_status)
	frappe.db.commit()
	return {"job": job, "status": new_status}


# ---------------------------------------------------------------------------
# Management Dashboard — KPI stats, charts data, and recent jobs
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_dashboard_data():
	"""Powers the Management Dashboard page. Returns stats cards,
	chart data, and the most recent jobs in one call."""
	now = frappe.utils.nowdate()

	# --- Stats ---
	active_statuses = [
		"Job Created", "Indent Raised", "In Purchase", "In Production",
		"In Packaging", "Material Consumption Pending", "Material Consumed",
		"Dispatched", "Installed",
	]
	active_jobs = frappe.db.count("Job", {"status": ["in", active_statuses]})
	in_production = frappe.db.count("Job", {"status": ["in", ["In Production", "In Packaging"]]})
	pending_indents = frappe.db.count("Material Indent", {"docstatus": 0})

	qr_totals = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(completed_qty), 0) AS done,
		       COALESCE(SUM(total_qty), 0) AS total
		FROM `tabQR Code Master`
		""",
		as_dict=True,
	)[0]
	qr_completion_pct = round((qr_totals.done / qr_totals.total * 100), 1) if qr_totals.total else 0

	revenue_row = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(grand_total), 0) AS total
		FROM `tabSales Invoice`
		WHERE docstatus != 2
		""",
	)[0]
	total_revenue = revenue_row[0] if revenue_row else 0

	cost_row = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(mi.total_indent_value), 0) AS indent
		FROM `tabMaterial Indent` mi WHERE mi.docstatus = 1
		""",
	)[0]
	total_indent_value = cost_row[0] if cost_row else 0

	design_cost = frappe.db.sql("SELECT COALESCE(SUM(design_cost), 0) FROM `tabDesign Task`")[0][0]
	data_entry_cost = frappe.db.sql("SELECT COALESCE(SUM(data_entry_cost), 0) FROM `tabData Entry Task`")[0][0]
	production_cost = frappe.db.sql("SELECT COALESCE(SUM(production_cost), 0) FROM `tabProduction Entry` WHERE docstatus=1")[0][0]
	packaging_cost = frappe.db.sql("SELECT COALESCE(SUM(packaging_cost), 0) FROM `tabPackaging Entry` WHERE docstatus=1")[0][0]
	dispatch_cost = frappe.db.sql("SELECT COALESCE(SUM(dispatch_cost), 0) FROM `tabDispatch Entry` WHERE docstatus=1")[0][0]
	total_manpower = (design_cost or 0) + (data_entry_cost or 0) + (production_cost or 0) + (packaging_cost or 0) + (dispatch_cost or 0)
	total_cost = total_indent_value + total_manpower
	avg_margin_pct = round(((total_revenue - total_cost) / total_revenue * 100), 1) if total_revenue else 0

	overdue_jobs = frappe.db.count(
		"Job",
		{
			"due_date": ["<", now],
			"status": ["in", active_statuses],
		},
	)

	stats = {
		"active_jobs": active_jobs,
		"in_production": in_production,
		"pending_indents": pending_indents,
		"qr_completion_pct": qr_completion_pct,
		"total_revenue": total_revenue,
		"total_cost": total_cost,
		"avg_margin_pct": avg_margin_pct,
		"overdue_jobs": overdue_jobs,
	}

	# --- Charts ---
	status_rows = frappe.db.sql(
		"""
		SELECT status AS label, COUNT(*) AS value
		FROM `tabJob`
		WHERE status != 'Cancelled'
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	from dateutil.relativedelta import relativedelta

	monthly_jobs = []
	for i in range(5, -1, -1):
		month_start = (frappe.utils.getdate(now) - relativedelta(months=i)).replace(day=1)
		month_end = month_start + relativedelta(months=1)
		label = month_start.strftime("%b %Y")
		created = frappe.db.count("Job", [["creation", ">=", str(month_start)], ["creation", "<", str(month_end)]])
		closed = frappe.db.count("Job", [["status", "=", "Closed"], ["modified", ">=", str(month_start)], ["modified", "<", str(month_end)]])
		monthly_jobs.append({"label": label, "created": created, "closed": closed})

	dept_rows = frappe.db.sql(
		"""
		SELECT to_department AS label, COUNT(*) AS value
		FROM `tabDepartment Transfer`
		WHERE status IN ('Pending Dispatch', 'In Transit', 'Qty Mismatch')
		GROUP BY to_department
		ORDER BY value DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	charts = {
		"jobs_by_status": status_rows,
		"monthly_jobs": monthly_jobs,
		"department_activity": dept_rows,
	}

	recent = frappe.get_all(
		"Job",
		fields=["name", "job_name", "customer", "status", "due_date"],
		order_by="modified desc",
		limit_page_length=15,
	)
	for j in recent:
		qr = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(completed_qty), 0) AS done,
			       COALESCE(SUM(total_qty), 0) AS total
			FROM `tabQR Code Master` WHERE job = %s
			""",
			j.name,
			as_dict=True,
		)[0]
		j["qr_pct"] = round((qr.done / qr.total * 100), 1) if qr.total else 0
		j["packed_boxes"] = frappe.db.count("Packing Box", {"job": j.name, "status": ["in", ["Packed", "Dispatched", "Received at Site", "Installed"]]})
		j["total_boxes"] = frappe.db.count("Packing Box", {"job": j.name})

	return {"stats": stats, "charts": charts, "recent_jobs": recent}


# ---------------------------------------------------------------------------
# Work from Home Request — apply, approve, reject, cancel
# ---------------------------------------------------------------------------

@frappe.whitelist()
def apply_wfh(employee, from_date, to_date, reason):
	"""Employee applies for Work from Home. Creates a WFH Request
	in Open status, awaiting manager/HR approval."""
	doc = frappe.get_doc(
		{
			"doctype": "Work from Home Request",
			"employee": employee,
			"from_date": from_date,
			"to_date": to_date,
			"reason": reason,
			"status": "Open",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve_wfh(wfh_request):
	"""Approve a WFH Request. Creates Attendance records for each
	approved WFH date, marking the employee as Present."""
	from elemental_erp.elemental_erp.doctype.work_from_home_request.work_from_home_request import (
		approve_wfh_request,
	)
	return approve_wfh_request(wfh_request)


@frappe.whitelist()
def reject_wfh(wfh_request, reason=None):
	"""Reject a WFH Request."""
	from elemental_erp.elemental_erp.doctype.work_from_home_request.work_from_home_request import (
		reject_wfh_request,
	)
	return reject_wfh_request(wfh_request, reason)


@frappe.whitelist()
def cancel_wfh(wfh_request):
	"""Cancel a WFH Request (employee or HR can cancel an Open request)."""
	doc = frappe.get_doc("Work from Home Request", wfh_request)
	if doc.status not in ("Open",):
		frappe.throw(f"Cannot cancel — this request is {doc.status}.")
	doc.status = "Cancelled"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def get_my_wfh_requests(employee, limit=20):
	"""Get the current employee's recent WFH requests."""
	return frappe.get_all(
		"Work from Home Request",
		filters={"employee": employee},
		fields=["name", "from_date", "to_date", "total_days", "reason",
		        "status", "approved_by", "approved_on", "attendance_marked"],
		order_by="modified desc",
		limit_page_length=limit,
	)


@frappe.whitelist()
def get_pending_wfh_approvals():
	"""Get WFH requests pending approval (for managers/HR)."""
	return frappe.get_all(
		"Work from Home Request",
		filters={"status": "Open"},
		fields=["name", "employee", "employee_name", "department",
		        "from_date", "to_date", "total_days", "reason", "creation"],
		order_by="creation asc",
	)


# ---------------------------------------------------------------------------
# Salary Slip OT calculation for Workers
# ---------------------------------------------------------------------------

@frappe.whitelist()
def calculate_slip_ot(employee, start_date, end_date):
	"""Calculate OT hours and amount for a Worker's Salary Slip.
	Called from the Salary Slip client script.

	Returns: ot_hours, hourly_rate, ot_amount, and formatted versions."""
	from elemental_erp.utils.worker_overtime import (
		hourly_rate, daily_rate, compute_daily_ot,
		GOV_OT_CAP_HOURS, STANDARD_SHIFT, get_days_in_month,
	)
	from frappe.utils import getdate, date_diff, add_days

	has_cat = frappe.db.column_exists("Employee", "employee_category")
	fields = ["ctc", "standard_shift_hours"]
	if has_cat:
		fields.append("employee_category")
	emp = frappe.db.get_value("Employee", employee, fields, as_dict=True)
	if not emp:
		return None
	if has_cat and emp.employee_category != "Worker":
		return None

	_start = getdate(start_date)
	_end = getdate(end_date)
	year = _start.year
	month = _start.month

	hr = hourly_rate(employee, year, month)

	# Calculate OT for each day in the slip period
	total_ot_hours = 0
	current = _start
	while current <= _end:
		date_str = str(current)

		# Check if holiday
		is_holiday = False
		holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
		if holiday_list:
			is_holiday = frappe.db.exists(
				"Holiday",
				{"parent": holiday_list, "holiday_date": date_str},
			)

		# Check if weekend
		is_weekend = current.weekday() >= 5
		is_day_off = is_holiday or is_weekend

		result = compute_daily_ot(employee, date_str, is_holiday=is_day_off)
		if result and result["status"] == "P":
			total_ot_hours += result["ot_hours"]

		current = add_days(current, 1)

	# Apply government cap (max 15 hrs)
	capped_ot_hours = min(total_ot_hours, GOV_OT_CAP_HOURS)

	# OT Amount = Capped Hours × Hourly Rate × 2 (at 2× rate)
	ot_amount = round(capped_ot_hours * hr * 2, 2)

	def fmt_hhmm(hours):
		h = int(hours)
		m = int(round((hours - h) * 60))
		return f"{h}:{m:02d}"

	return {
		"ot_hours": round(capped_ot_hours, 2),
		"ot_hours_fmt": fmt_hhmm(capped_ot_hours),
		"hourly_rate": round(hr, 2),
		"ot_amount": ot_amount,
		"ot_amount_fmt": frappe.format_currency(ot_amount),
		"total_ot_actual": round(total_ot_hours, 2),
		"total_ot_actual_fmt": fmt_hhmm(total_ot_hours),
	}


# ── Installation Self-Checkin APIs ─────────────────────────────────────


@frappe.whitelist(allow_guest=True)
def lookup_employee_by_qr(qr_or_code):
	"""Look up employee by QR value or employee code.
	Returns employee info for the self-checkin page."""
	# Try QR value first
	has_cat = frappe.db.column_exists("Employee", "employee_category")
	_emp_fields = ["name", "employee_name", "department", "designation"]
	if has_cat:
		_emp_fields.append("employee_category")

	emp = frappe.db.get_value(
		"Employee",
		{"employee_qr_value": qr_or_code},
		_emp_fields,
		as_dict=True,
	)
	if not emp:
		# Try by employee name/code
		emp = frappe.db.get_value(
			"Employee",
			{"name": qr_or_code},
			_emp_fields,
			as_dict=True,
		)
	if not emp:
		return {"found": False}

	return {
		"found": True,
		"employee": emp.name,
		"employee_name": emp.employee_name,
		"department": emp.department or "",
		"designation": emp.designation or "",
		"category": getattr(emp, "employee_category", None) or "",
	}


@frappe.whitelist()
def installation_self_checkin(employee, action, photo=None, latitude=None, longitude=None, address=""):
	"""Create an Employee Checkin from the mobile self-checkin page.
	
	Args:
	    employee: Employee name/code
	    action: 'IN' or 'OUT'
	    photo: base64 data URL of the site photo
	    latitude: GPS latitude
	    longitude: GPS longitude
	    address: Site address/landmark text
		"""
	if action not in ("IN", "OUT"):
		return {"success": False, "message": "Invalid action. Must be IN or OUT."}

	# Verify employee exists
	emp_name = frappe.db.get_value("Employee", employee, "name")
	if not emp_name:
		# Try by QR value
		emp_name = frappe.db.get_value("Employee", {"employee_qr_value": employee}, "name")
	if not emp_name:
		return {"success": False, "message": f"Employee not found: {employee}"}

	# Save photo as file if provided
	photo_url = None
	if photo:
		try:
			import base64
			# Handle data URL format
			if photo.startswith("data:"):
				header, data = photo.split(",", 1)
				file_ext = "jpg"
				if "png" in header:
					file_ext = "png"
			else:
				data = photo
				file_ext = "jpg"

			file_data = base64.b64decode(data)
			file_name = f"checkin_{emp_name}_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.{file_ext}"

			# Save to temp path and create File document
			import os
			tmp_path = os.path.join(frappe.get_site_path("private", "files"), file_name)
			with open(tmp_path, "wb") as f:
				f.write(file_data)

			# Create File document
			file_doc = frappe.get_doc({
				"doctype": "File",
				"file_name": file_name,
				"is_private": 1,
				"file_url": f"/private/files/{file_name}",
				"attached_to_doctype": "Employee Checkin",
			})
			file_doc.insert(ignore_permissions=True)
			photo_url = file_doc.file_url
		except Exception as e:
			frappe.log_error(title="Installation Checkin - Photo save", message=str(e))

	# Create Employee Checkin
	checkin = frappe.get_doc({
		"doctype": "Employee Checkin",
		"employee": emp_name,
		"log_type": action,
		"time": frappe.utils.now_datetime(),
		"skip_auto_attendance": 0,
		"latitude": latitude,
		"longitude": longitude,
		"checkin_photo": photo_url,
		"checkin_address": address,
		"checkin_source": "Self (Mobile)",
	})
	checkin.insert(ignore_permissions=True)

	# Auto-create attendance
	from elemental_erp.employee_gate import upsert_attendance_for_day
	today = frappe.utils.nowdate()
	upsert_attendance_for_day(emp_name, today)

	emp_name_display = frappe.db.get_value("Employee", emp_name, "employee_name")
	log_time = frappe.utils.format_datetime(frappe.utils.now_datetime(), "hh:mm a")

	return {
		"success": True,
		"message": f"{action} recorded for {emp_name_display} at {log_time}",
		"checkin_name": checkin.name,
	}


@frappe.whitelist(allow_guest=True)
def get_today_checkins():
	"""Get today's checkins for the recent list on the self-checkin page."""
	today = frappe.utils.nowdate()
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"time": ["between", [f"{today} 00:00:00", f"{today} 23:59:59"]],
		},
		fields=["employee", "employee_name", "log_type", "time", "checkin_source", "checkin_photo"],
		order_by="time desc",
		limit_page_length=20,
	)
	result = []
	for c in checkins:
		result.append({
			"employee": c.employee,
			"employee_name": c.employee_name,
			"log_type": c.log_type,
			"time": frappe.utils.format_datetime(c.time, "hh:mm a"),
			"source": c.checkin_source or "Gate QR",
			"has_photo": bool(c.checkin_photo),
		})
	return result
