import io

import frappe
import qrcode
from frappe.utils.file_manager import save_file
from PIL import Image, ImageDraw, ImageFont


def generate_qr_image(qr_value, scan_url, attached_to_doctype, attached_to_name, label=None):
	"""Render a QR image (encoding the scan URL) and attach it to the given doc.
	An optional human-readable label is drawn below the QR without changing the
	encoded scan value. Returns the file_url so the caller can store it on a field."""
	img = qrcode.make(scan_url)
	if label:
		img = img.convert("RGB")
		font = ImageFont.load_default()
		text = str(label)
		draw = ImageDraw.Draw(img)
		bbox = draw.textbbox((0, 0), text, font=font)
		text_width = bbox[2] - bbox[0]
		text_height = bbox[3] - bbox[1]
		caption_height = text_height + 18
		labelled = Image.new("RGB", (img.width, img.height + caption_height), "white")
		labelled.paste(img, (0, 0))
		label_draw = ImageDraw.Draw(labelled)
		label_draw.text(
			((img.width - text_width) / 2, img.height + 7),
			text,
			fill="black",
			font=font,
		)
		img = labelled
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
