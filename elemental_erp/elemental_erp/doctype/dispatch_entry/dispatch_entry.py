import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost
from elemental_erp.utils.transactions import advance_job_status, assert_active_job


class DispatchEntry(Document):
	def validate(self):
		assert_active_job(self.job)
		self.dispatch_cost = compute_cost(self.employee, self.hours_spent)
		if self.dispatch_status in ("Dispatched", "Delivered"):
			total = frappe.db.count("Packing Box", {"job": self.job})
			if not total:
				frappe.throw("Dispatch requires at least one Packing Box.")
			allowed = ["Dispatched", "Received at Site", "Installed"]
			remaining = frappe.db.count(
				"Packing Box", {"job": self.job, "status": ["not in", allowed]}
			)
			if remaining:
				frappe.throw(f"{remaining} Packing Box(es) have not been dispatched.")
		if self.dispatch_status == "Delivered":
			undelivered = frappe.db.count(
				"Packing Box", {"job": self.job, "status": ["not in", ["Received at Site", "Installed"]]}
			)
			if undelivered:
				frappe.throw(f"{undelivered} Packing Box(es) have not been received at site.")

	def on_submit(self):
		if self.dispatch_status in ("Dispatched", "Delivered"):
			advance_job_status(self.job, "Dispatched")
