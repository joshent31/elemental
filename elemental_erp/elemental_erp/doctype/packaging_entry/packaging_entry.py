import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost
from elemental_erp.elemental_erp.doctype.qc_inspection.qc_inspection import qc_passed


class PackagingEntry(Document):
	def validate(self):
		self.packaging_cost = compute_cost(self.employee, self.hours_spent)

		finished_good = frappe.db.get_value("QR Code Master", self.qr_code_master, "finished_good")
		if finished_good and not qc_passed(self.job, finished_good):
			frappe.throw(
				f"QC Inspection has not Passed yet for {finished_good} on this Job \u2014 "
				f"packaging is blocked until QC scans it Passed (see /qc-scan)."
			)

	def on_submit(self):
		frappe.get_doc(
			{
				"doctype": "QR Scan Log",
				"qr_code_master": self.qr_code_master,
				"department": "Packaging",
				"qty_scanned": 0,  # packing doesn't add to production completion, just logs a checkpoint
				"remarks": f"Packed {self.packed_qty} - Packaging Entry {self.name}",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Job", self.job, "status", "In Packaging")
