import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost
from elemental_erp.elemental_erp.doctype.qc_inspection.qc_inspection import qc_passed
from elemental_erp.utils.transactions import (
	advance_job_status,
	assert_active_job,
	assert_qr_belongs_to_job,
	positive_quantity,
)


class PackagingEntry(Document):
	def validate(self):
		assert_active_job(self.job)
		qr = assert_qr_belongs_to_job(self.qr_code_master, self.job)
		self.packed_qty = positive_quantity(self.packed_qty, "Packed Qty")
		if qr.status != "Completed":
			frappe.throw(f"QR Code Master {qr.name} is {qr.status}; production must be completed first.")
		self.packaging_cost = compute_cost(self.employee, self.hours_spent)

		finished_good = qr.finished_good
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
				"remarks": f"Packed {self.packed_qty} — Packaging Entry {self.name}",
			}
		).insert(ignore_permissions=True)
		advance_job_status(self.job, "In Packaging")
