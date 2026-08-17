import frappe
from frappe.model.document import Document


class QuotationElemental(Document):
	def validate(self):
		for row in self.items:
			row.amount = (row.qty or 0) * (row.rate or 0)
		self.total_quoted_value = sum((row.amount or 0) for row in self.items)

	def on_submit(self):
		if self.status == "Draft":
			self.status = "Sent to Customer"
