import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class VirtualFGReservation(Document):
	def validate(self):
		if flt(self.reserved_qty) <= 0:
			frappe.throw("Reserved Qty must be greater than zero.")
		lot = frappe.get_doc("Virtual FG Transfer", self.virtual_transfer)
		if lot.docstatus != 1 or lot.status == "Cancelled":
			frappe.throw("Select a submitted, available Virtual FG Transfer.")
		job = frappe.get_doc("Job", self.target_job)
		if job.customer != lot.customer:
			frappe.throw("Virtual stock is customer-isolated and cannot be allocated to another customer.")
		if not any(r.finished_good == lot.finished_good for r in job.fg_items):
			frappe.throw(f"{lot.finished_good} is not present on target Job {job.name}.")
		self.customer, self.finished_good, self.source_job = lot.customer, lot.finished_good, lot.source_job
		used = frappe.db.sql("""SELECT COALESCE(SUM(reserved_qty),0) FROM `tabVirtual FG Reservation`
			WHERE virtual_transfer=%s AND docstatus=1 AND name!=%s""", (lot.name, self.name or ""))[0][0]
		if flt(used) + flt(self.reserved_qty) > flt(lot.qty):
			frappe.throw(f"Only {flt(lot.qty)-flt(used)} is available in virtual lot {lot.name}.")

	def on_submit(self):
		self.db_set({"status":"Reserved","approved_by":frappe.session.user,"approved_on":now_datetime()})
		_refresh_lot_and_job(self.virtual_transfer, self.target_job, self.finished_good)

	def on_cancel(self):
		if flt(self.utilized_qty):
			frappe.throw("A utilized reservation cannot be cancelled. Reverse its Stock Entry first.")
		self.db_set("status", "Cancelled")
		_refresh_lot_and_job(self.virtual_transfer, self.target_job, self.finished_good)


def _refresh_lot_and_job(transfer, job, finished_good):
	lot = frappe.get_doc("Virtual FG Transfer", transfer)
	reserved, utilized = frappe.db.sql("""SELECT COALESCE(SUM(reserved_qty),0), COALESCE(SUM(utilized_qty),0)
		FROM `tabVirtual FG Reservation` WHERE virtual_transfer=%s AND docstatus=1""", transfer)[0]
	status = "Utilized" if flt(utilized) >= flt(lot.qty) else "Partly Utilized" if utilized else "Reserved" if flt(reserved) >= flt(lot.qty) else "Partly Reserved" if reserved else "Available"
	frappe.db.set_value("Virtual FG Transfer", transfer, "status", status, update_modified=False)
	row = frappe.db.get_value("Job FG Item", {"parent":job,"parenttype":"Job","finished_good":finished_good}, ["name","job_qty"], as_dict=True)
	if row:
		allocated = frappe.db.sql("""SELECT COALESCE(SUM(reserved_qty),0) FROM `tabVirtual FG Reservation`
			WHERE target_job=%s AND finished_good=%s AND docstatus=1 AND status!='Cancelled'""", (job, finished_good))[0][0]
		frappe.db.set_value("Job FG Item", row.name, {"virtual_stock_qty":flt(allocated),"production_qty":max(flt(row.job_qty)-flt(allocated),0)}, update_modified=False)
