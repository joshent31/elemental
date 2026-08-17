import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost


class DataEntryTask(Document):
	def validate(self):
		if self.hours_spent:
			# no dedicated Employee link on this doctype (assigned_to is a
			# User) - cost stays 0 unless assigned_to maps 1:1 to an Employee
			# with the same user_id; left simple and documented as a gap.
			employee = frappe.db.get_value("Employee", {"user_id": self.assigned_to}, "name")
			self.data_entry_cost = compute_cost(employee, self.hours_spent)
