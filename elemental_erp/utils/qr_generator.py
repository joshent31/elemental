import io

import frappe
import qrcode
from frappe.utils.file_manager import save_file


def generate_qr_image(qr_value, scan_url, attached_to_doctype, attached_to_name):
	"""Render a QR image (encoding the scan URL) and attach it to the given doc.
	Returns the file_url so the caller can store it on a field."""
	img = qrcode.make(scan_url)
	buf = io.BytesIO()
	img.save(buf, format="PNG")
	buf.seek(0)

	file_doc = save_file(
		fname=f"{qr_value}.png",
		content=buf.getvalue(),
		dt=attached_to_doctype,
		dn=attached_to_name,
		is_private=0,
	)
	return file_doc.file_url
