import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import (
	assert_active_job,
	assert_qr_belongs_to_job,
	assert_subpart_label_belongs_to_job,
	positive_quantity,
)


class PackingBox(Document):
	def validate(self):
		assert_active_job(self.job)
		if int(self.box_no or 0) <= 0 or int(self.total_boxes or 0) <= 0:
			frappe.throw("Box No and Total Boxes must be positive numbers.")
		if int(self.box_no) > int(self.total_boxes):
			frappe.throw("Box No cannot exceed Total Boxes.")
		existing = frappe.db.exists(
			"Packing Box", {"job": self.job, "box_no": self.box_no, "name": ["!=", self.name or ""]}
		)
		if existing:
			frappe.throw(f"Box {self.box_no} already exists for Job {self.job}.")
		for row in self.contents:
			if row.job_subpart_label:
				label = assert_subpart_label_belongs_to_job(row.job_subpart_label, self.job)
				row.subpart_label = label.subpart_name
				if row.qr_code_master:
					qr = assert_qr_belongs_to_job(row.qr_code_master, self.job)
					if (qr.finished_good, qr.subpart_code) != (
						label.finished_good,
						label.subpart_code,
					):
						frappe.throw(
							f"Process tracker {qr.name} does not belong to subpart label {label.name}."
						)
			elif row.qr_code_master:
				qr = assert_qr_belongs_to_job(row.qr_code_master, self.job)
				row.subpart_label = qr.get("subpart_name") or row.subpart_label
			else:
				frappe.throw("Each Packing Box Content row needs a Job Subpart Label or legacy QR tracker.")
			row.packed_qty = positive_quantity(row.packed_qty, "Packed Qty")
