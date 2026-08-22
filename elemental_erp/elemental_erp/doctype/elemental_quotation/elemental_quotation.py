import frappe
from frappe.model.document import Document


class ElementalQuotation(Document):
	def validate(self):
		for row in self.items:
			row.amount = (row.qty or 0) * (row.rate or 0)
		self.total_quoted_value = sum((row.amount or 0) for row in self.items)

	def before_submit(self):
		# Persist the status as part of Frappe's final submit database update.
		if self.status == "Draft":
			self.status = "Sent to Customer"
