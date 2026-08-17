import frappe
from frappe.model.document import Document

from elemental_erp.utils.qr_generator import generate_qr_image


class QRCodeMaster(Document):
	def update_status(self, qty_scanned):
		"""Called by QR Scan Log.apply_scan_to_qr_master to advance progress.
		Refuses scans that would push completed_qty past total_qty, instead
		of silently absorbing them - an over-scan is almost always a
		mistake (wrong QR, duplicate scan, wrong qty typed) and should stop
		the transaction rather than quietly break the completion %."""
		if qty_scanned and qty_scanned > 0:
			remaining = (self.total_qty or 0) - (self.completed_qty or 0)
			if qty_scanned > remaining + 1e-6:
				frappe.throw(
					f"This scan ({qty_scanned}) would take {self.subpart_name} / {self.process} "
					f"to {(self.completed_qty or 0) + qty_scanned}, past its total of {self.total_qty}. "
					f"Only {remaining} remain \u2014 check the QR and quantity."
				)

		self.completed_qty = (self.completed_qty or 0) + qty_scanned
		if self.completed_qty <= 0:
			self.status = "Pending"
		elif self.completed_qty >= (self.total_qty or 0):
			self.status = "Completed"
		else:
			self.status = "In Process"
		self.save(ignore_permissions=True)
		check_job_fully_completed(self.job)


def create_qr_master(job, finished_good, subpart_code, subpart_name, process, total_qty):
	"""Create one QR Code Master row and render its physical QR image."""
	qr_value = frappe.generate_hash(length=12).upper()

	doc = frappe.get_doc(
		{
			"doctype": "QR Code Master",
			"job": job,
			"finished_good": finished_good,
			"subpart_code": subpart_code,
			"subpart_name": subpart_name,
			"process": process,
			"total_qty": total_qty,
			"completed_qty": 0,
			"status": "Pending",
			"qr_value": qr_value,
		}
	)
	doc.insert(ignore_permissions=True)

	scan_url = frappe.utils.get_url(f"/qr/{qr_value}")
	doc.scan_url = scan_url
	file_url = generate_qr_image(qr_value, scan_url, doc.doctype, doc.name)
	doc.qr_image = file_url
	doc.save(ignore_permissions=True)
	return doc


def check_job_fully_completed(job_name):
	"""If every QR Code Master for this Job is Completed, flip Job status
	and fire the 'ready for dispatch' notification (see notification fixture)."""
	pending = frappe.db.count(
		"QR Code Master", {"job": job_name, "status": ["!=", "Completed"]}
	)
	if pending == 0:
		frappe.db.set_value("Job", job_name, "status", "In Packaging")
