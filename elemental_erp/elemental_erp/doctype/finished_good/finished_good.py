import frappe
from frappe.model.document import Document


class FinishedGood(Document):
	def validate(self):
		if not self.subparts:
			frappe.msgprint(
				"No subparts added — QR tracking will be generated at the Finished-Good level only.",
				alert=True,
			)
