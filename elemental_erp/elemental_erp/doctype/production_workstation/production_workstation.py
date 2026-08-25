import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class ProductionWorkstation(Document):
	def before_validate(self):
		if not (self.workstation_code or "").strip():
			self.workstation_code = make_autoname(self.naming_series or "WS-.#####")

	def validate(self):
		self.workstation_code = (self.workstation_code or "").strip().upper()
		if not self.workstation_code:
			frappe.throw("Machine / Table Code is required.")

	def after_insert(self):
		self.ensure_qr()

	def ensure_qr(self):
		from elemental_erp.utils.qr_generator import generate_qr_image

		qr_value = self.qr_value or frappe.generate_hash(length=16).upper()
		while frappe.db.exists("Production Workstation", {"qr_value": qr_value, "name": ["!=", self.name]}):
			qr_value = frappe.generate_hash(length=16).upper()
		scan_url = frappe.utils.get_url(f"/worker-job-scan?workstation={qr_value}")
		qr_image = self.qr_image or generate_qr_image(
			qr_value, scan_url, self.doctype, self.name
		)
		frappe.db.set_value(
			self.doctype,
			self.name,
			{"qr_value": qr_value, "scan_url": scan_url, "qr_image": qr_image},
			update_modified=False,
		)
