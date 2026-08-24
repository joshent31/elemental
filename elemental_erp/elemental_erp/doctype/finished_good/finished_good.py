import frappe
from frappe.model.document import Document


class FinishedGood(Document):
	def validate(self):
		if not self.subparts:
			frappe.msgprint(
				"No subparts added — QR tracking will be generated at the Finished-Good level only.",
				alert=True,
			)
			return

		seen_codes = set()
		for row in self.subparts:
			part_code = (row.part_code or "").strip()
			if part_code in seen_codes:
				frappe.throw(f"Subpart code {part_code} is listed more than once in this Finished Good.")
			seen_codes.add(part_code)
			if float(row.qty_per_fg or 0) <= 0:
				frappe.throw(f"Qty per FG must be greater than zero for subpart {part_code}.")
