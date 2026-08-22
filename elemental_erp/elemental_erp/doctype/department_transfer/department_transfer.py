import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import assert_active_job, assert_qr_belongs_to_job, positive_quantity


class DepartmentTransfer(Document):
	def validate(self):
		assert_active_job(self.job)
		assert_qr_belongs_to_job(self.qr_code_master, self.job)
		self.transfer_qty = positive_quantity(self.transfer_qty, "Transfer Qty")
		if self.from_department == self.to_department:
			frappe.throw("From Department and To Department must be different.")
		if self.received_qty:
			self.received_qty = positive_quantity(self.received_qty, "Received Qty")
		self.compute_diff()

	def compute_diff(self):
		self.qty_diff = (self.transfer_qty or 0) - (self.received_qty or 0)
