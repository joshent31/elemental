import frappe
from frappe.model.document import Document


class QRScanLog(Document):
	pass


def apply_scan_to_qr_master(doc, method=None):
	"""hooked on QR Scan Log.after_insert (see hooks.py)."""
	qr_master = frappe.get_doc("QR Code Master", doc.qr_code_master)
	qr_master.update_status(doc.qty_scanned)
