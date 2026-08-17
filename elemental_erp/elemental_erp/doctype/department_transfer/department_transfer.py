import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class DepartmentTransfer(Document):
	def compute_diff(self):
		self.qty_diff = (self.transfer_qty or 0) - (self.received_qty or 0)
