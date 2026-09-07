import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class VirtualFGTransfer(Document):
	def validate(self):
		if flt(self.qty) <= 0:
			frappe.throw("Transfer Qty must be greater than zero.")
		job = frappe.get_doc("Job", self.source_job)
		self.customer = job.customer
		if not any(r.finished_good == self.finished_good for r in job.fg_items):
			frappe.throw(f"Finished Good {self.finished_good} is not on Job {self.source_job}.")
		job_qty = next(flt(r.job_qty) for r in job.fg_items if r.finished_good == self.finished_good)
		already_moved = flt(frappe.db.sql("""SELECT COALESCE(SUM(qty),0) FROM `tabVirtual FG Transfer`
			WHERE source_job=%s AND finished_good=%s AND docstatus=1 AND name!=%s""",
			(self.source_job, self.finished_good, self.name or ""))[0][0])
		already_packed = flt(frappe.db.sql("""SELECT COALESCE(SUM(c.qty),0) FROM `tabPacking Box Content` c
			JOIN `tabPacking Box` b ON b.name=c.parent WHERE b.job=%s AND c.finished_good=%s
			AND b.status NOT IN ('Cancelled','Label Created')""", (self.source_job, self.finished_good))[0][0])
		available = max(job_qty - already_moved - already_packed, 0)
		if flt(self.qty) > available:
			frappe.throw(f"Only {available} undispatched and unpacked {self.finished_good} is available on {self.source_job}.")
		item = frappe.db.get_value("Finished Good", self.finished_good, "erpnext_item")
		if not item:
			frappe.throw(f"Map {self.finished_good} to a stock Item before transferring it.")
		self.erpnext_item = item
		settings = frappe.get_single("Elemental Stock Settings")
		self.company = settings.company
		self.virtual_warehouse = settings.virtual_fg_warehouse
		if not self.source_warehouse or not self.virtual_warehouse:
			frappe.throw("Configure source and Virtual Finished Goods warehouses.")
		if self.source_warehouse == self.virtual_warehouse:
			frappe.throw("Source and Virtual Finished Goods warehouses must differ.")

	def on_submit(self):
		stock_entry = frappe.get_doc({
			"doctype":"Stock Entry", "stock_entry_type":"Material Transfer", "company":self.company,
			"remarks":f"Customer-isolated virtual FG transfer {self.name}; source Job {self.source_job}",
			"items":[{"item_code":self.erpnext_item,"qty":self.qty,"s_warehouse":self.source_warehouse,"t_warehouse":self.virtual_warehouse}],
		}).insert(ignore_permissions=True)
		stock_entry.submit()
		self.db_set({"stock_entry":stock_entry.name,"status":"Available","approved_by":frappe.session.user,"approved_on":now_datetime()})

	def on_cancel(self):
		if frappe.db.exists("Virtual FG Reservation", {"virtual_transfer":self.name,"docstatus":1}):
			frappe.throw("Cancel linked submitted reservations before cancelling this transfer.")
		if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 1:
			frappe.get_doc("Stock Entry", self.stock_entry).cancel()
		self.db_set("status", "Cancelled")
