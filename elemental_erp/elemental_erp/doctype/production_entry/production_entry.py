import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost
from elemental_erp.utils.transactions import (
	advance_job_status,
	assert_active_job,
	assert_qr_belongs_to_job,
	positive_quantity,
)


class ProductionEntry(Document):
	def validate(self):
		assert_active_job(self.job)
		assert_qr_belongs_to_job(self.qr_code_master, self.job)
		self.produced_qty = positive_quantity(self.produced_qty, "Produced Qty")
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
		advance_job_status(self.job, "In Production")

	def on_cancel(self):
		qr_master = frappe.get_doc("QR Code Master", self.qr_code_master)
		qr_master.reverse_status(self.produced_qty)
