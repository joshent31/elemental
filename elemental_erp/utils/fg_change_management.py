from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime, today


PACKAGING_APPROVERS = {"System Manager", "Elemental Packaging HOD"}


def _html_table(rows, headers):
	head = "".join(f"<th>{escape(str(value))}</th>" for value in headers)
	body = "".join("<tr>" + "".join(f"<td>{escape(str(value if value is not None else ''))}</td>" for value in row) + "</tr>" for row in rows)
	return f"<table border='1' cellpadding='5' cellspacing='0'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _require_packaging_approval():
	if not PACKAGING_APPROVERS.intersection(frappe.get_roles()):
		frappe.throw(_("Only Packaging HOD or System Manager can approve virtual stock movements."), frappe.PermissionError)


@frappe.whitelist()
def get_virtual_availability(customer, finished_good, intended_location=None):
	conditions = ["t.docstatus=1", "t.customer=%s", "t.finished_good=%s", "t.status!='Cancelled'"]
	values = [customer, finished_good]
	if intended_location:
		conditions.append("t.intended_location=%s")
		values.append(intended_location)
	return frappe.db.sql(f"""
		SELECT t.name, t.source_job, t.intended_location, t.qty,
			t.qty-COALESCE(SUM(CASE WHEN r.docstatus=1 THEN r.reserved_qty ELSE 0 END),0) AS available_qty,
			t.creation AS available_since
		FROM `tabVirtual FG Transfer` t
		LEFT JOIN `tabVirtual FG Reservation` r ON r.virtual_transfer=t.name
		WHERE {' AND '.join(conditions)}
		GROUP BY t.name HAVING available_qty>0 ORDER BY t.creation
	""", values, as_dict=True)


@frappe.whitelist()
def get_job_virtual_availability(job):
	job_doc = frappe.get_doc("Job", job)
	job_doc.check_permission("read")
	result = []
	for row in job_doc.fg_items:
		lots = get_virtual_availability(job_doc.customer, row.finished_good)
		available = sum(flt(lot.available_qty) for lot in lots)
		result.append({"finished_good":row.finished_good,"required_qty":flt(row.job_qty),
			"available_qty":available,"suggested_production_qty":max(flt(row.job_qty)-available,0),"lots":lots})
	return result


@frappe.whitelist()
def reserve_virtual_stock(virtual_transfer, target_job, qty, reason):
	_require_packaging_approval()
	doc = frappe.get_doc({"doctype":"Virtual FG Reservation", "virtual_transfer":virtual_transfer,
		"target_job":target_job, "reserved_qty":flt(qty), "reason":reason})
	doc.insert()
	doc.submit()
	return doc.name


@frappe.whitelist()
def utilize_virtual_stock(reservation, qty=None, target_warehouse=None):
	_require_packaging_approval()
	doc = frappe.get_doc("Virtual FG Reservation", reservation)
	if doc.docstatus != 1 or doc.status not in ("Reserved", "Partly Utilized"):
		frappe.throw(_("Reservation must be submitted and available."))
	remaining = flt(doc.reserved_qty) - flt(doc.utilized_qty)
	move_qty = flt(qty or remaining)
	if move_qty <= 0 or move_qty > remaining:
		frappe.throw(_("Utilization quantity must be between 0 and {0}.").format(remaining))
	lot = frappe.get_doc("Virtual FG Transfer", doc.virtual_transfer)
	settings = frappe.get_single("Elemental Stock Settings")
	target = target_warehouse or doc.target_warehouse or settings.default_target_warehouse
	if not target or target == lot.virtual_warehouse:
		frappe.throw(_("Select a target warehouse different from the virtual warehouse."))
	entry = frappe.get_doc({
		"doctype":"Stock Entry", "stock_entry_type":"Material Transfer", "company":lot.company,
		"remarks":f"Virtual FG utilization {doc.name}; {lot.source_job} -> {doc.target_job}",
		"items":[{"item_code":lot.erpnext_item,"qty":move_qty,"s_warehouse":lot.virtual_warehouse,"t_warehouse":target}],
	}).insert(ignore_permissions=True)
	entry.submit()
	new_used = flt(doc.utilized_qty) + move_qty
	doc.db_set({"utilized_qty":new_used,"target_warehouse":target,"stock_entry":entry.name,
		"status":"Utilized" if new_used >= flt(doc.reserved_qty) else "Partly Utilized"})
	from elemental_erp.elemental_erp.doctype.virtual_fg_reservation.virtual_fg_reservation import _refresh_lot_and_job
	_refresh_lot_and_job(doc.virtual_transfer, doc.target_job, doc.finished_good)
	return entry.name


def sync_cancelled_stock_entry(doc, method=None):
	reservation = frappe.db.get_value("Virtual FG Reservation", {"stock_entry":doc.name,"docstatus":1}, "name")
	if reservation:
		res = frappe.get_doc("Virtual FG Reservation", reservation)
		res.db_set({"utilized_qty":0,"stock_entry":None,"status":"Reserved"})
		from elemental_erp.elemental_erp.doctype.virtual_fg_reservation.virtual_fg_reservation import _refresh_lot_and_job
		_refresh_lot_and_job(res.virtual_transfer, res.target_job, res.finished_good)


def _non_worker_employee_emails():
	meta = frappe.get_meta("Employee")
	has_category = meta.has_field("employee_category")
	fields = ["user_id", "company_email", "personal_email"] + (["employee_category"] if has_category else [])
	emails = set()
	for employee in frappe.get_all("Employee", filters={"status":"Active"}, fields=fields, limit_page_length=0):
		if has_category and (employee.employee_category or "").strip().lower() == "worker":
			continue
		address = employee.user_id or employee.company_email or employee.personal_email
		if address:
			emails.add(address)
	return sorted(emails)


def send_daily_fg_change_digest():
	settings = frappe.get_single("Elemental Stock Settings")
	if not settings.send_daily_fg_digest:
		return
	day = add_days(today(), -1)
	rows = frappe.db.sql("""
		SELECT job, customer, finished_good,
			SUBSTRING_INDEX(GROUP_CONCAT(original_qty ORDER BY changed_on ASC), ',', 1) original_qty,
			SUBSTRING_INDEX(GROUP_CONCAT(new_qty ORDER BY changed_on DESC), ',', 1) new_qty,
			GROUP_CONCAT(DISTINCT changed_by ORDER BY changed_by SEPARATOR ', ') changed_by
		FROM `tabJob FG Change Log` WHERE DATE(changed_on)=%s
		GROUP BY job, customer, finished_good ORDER BY job, finished_good
	""", day, as_dict=True)
	rows = [r for r in rows if abs(flt(r.new_qty)-flt(r.original_qty)) > 1e-9]
	if not rows:
		return
	data = [[r.job, r.customer, r.finished_good, r.original_qty, r.new_qty,
		f"{flt(r.new_qty)-flt(r.original_qty):+g}", r.changed_by] for r in rows]
	html = _html_table(data, ["Job","Customer","FG","Original Qty","Final Qty","Net Change","Changed By"])
	recipients = _non_worker_employee_emails()
	if recipients:
		frappe.sendmail(recipients=recipients, subject=f"Finished Good changes - {day}", message=html)


def send_virtual_stock_ageing_alerts():
	settings = frappe.get_single("Elemental Stock Settings")
	if not settings.send_ageing_alert:
		return
	cutoff = add_days(today(), -int(settings.ageing_days or 30))
	rows = frappe.db.sql("""SELECT name, source_job, customer, finished_good, qty, intended_location, creation
		FROM `tabVirtual FG Transfer` WHERE docstatus=1 AND status IN ('Available','Partly Reserved') AND DATE(creation)<=%s""", cutoff, as_dict=True)
	if not rows:
		return
	recipients = _non_worker_employee_emails()
	if recipients:
		frappe.sendmail(recipients=recipients, subject="Unused virtual finished goods ageing alert",
			message=_html_table([[r.name,r.source_job,r.customer,r.finished_good,r.qty,r.intended_location,getdate(r.creation)] for r in rows],
			["Lot","Source Job","Customer","FG","Qty","Location","Available Since"]))
