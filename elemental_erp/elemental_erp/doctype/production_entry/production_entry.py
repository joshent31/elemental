import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost


class ProductionEntry(Document):
	def validate(self):
		self.production_cost = compute_cost(self.employee, self.hours_spent)

	def on_submit(self):
		# Log a QR scan so QR Code Master status advances automatically
		frappe.get_doc(
			{
				"doctype": "QR Scan Log",
				"qr_code_master": self.qr_code_master,
				"department": "Production",
				"qty_scanned": self.produced_qty,
				"remarks": f"Auto-logged from Production Entry {self.name}",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Job", self.job, "status", "In Production")
