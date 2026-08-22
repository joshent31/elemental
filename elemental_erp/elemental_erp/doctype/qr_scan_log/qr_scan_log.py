import frappe
from frappe.model.document import Document


class QRScanLog(Document):
	def validate(self):
		if float(self.qty_scanned or 0) < 0:
			frappe.throw("QR Scan Log quantity cannot be negative.")


def apply_scan_to_qr_master(doc, method=None):
	"""hooked on QR Scan Log.after_insert (see hooks.py)."""
	qty = float(doc.qty_scanned or 0)
	if qty < 0:
		frappe.throw("QR Scan Log quantity cannot be negative.")
	if qty == 0:
		return
	qr_master = frappe.get_doc("QR Code Master", doc.qr_code_master)
	qr_master.update_status(qty)
