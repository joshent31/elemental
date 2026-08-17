import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost


class DispatchEntry(Document):
	def validate(self):
		self.dispatch_cost = compute_cost(self.employee, self.hours_spent)

	def on_submit(self):
		if self.dispatch_status == "Dispatched":
			frappe.db.set_value("Job", self.job, "status", "Dispatched")
		elif self.dispatch_status == "Delivered":
			frappe.db.set_value("Job", self.job, "status", "Closed")
