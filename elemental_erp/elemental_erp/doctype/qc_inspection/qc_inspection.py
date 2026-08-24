import frappe
from frappe.model.document import Document

from elemental_erp.utils.qr_generator import generate_qr_image
from elemental_erp.utils.transactions import assert_active_job


class QCInspection(Document):
	def validate(self):
		assert_active_job(self.job)


def get_or_create_qc_inspection(job, finished_good):
	"""Return the one Job/FG QC label, creating its physical QR if missing."""
	existing = frappe.db.get_value(
		"QC Inspection",
		{"job": job, "finished_good": finished_good},
		"name",
	)
	if existing:
		doc = frappe.get_doc("QC Inspection", existing)
		if not doc.get("qr_value"):
			doc.qr_value = frappe.generate_hash(length=12).upper()
		if not doc.get("qr_image"):
			doc.qr_image = generate_qr_image(
				doc.qr_value,
				frappe.utils.get_url(f"/qc-scan?qr={doc.qr_value}"),
				doc.doctype,
				doc.name,
			)
			doc.save(ignore_permissions=True)
		return doc

	doc = frappe.get_doc(
		{
			"doctype": "QC Inspection",
			"job": job,
			"finished_good": finished_good,
			"status": "Pending",
			"qr_value": frappe.generate_hash(length=12).upper(),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.qr_image = generate_qr_image(
		doc.qr_value,
		frappe.utils.get_url(f"/qc-scan?qr={doc.qr_value}"),
		doc.doctype,
		doc.name,
	)
	doc.save(ignore_permissions=True)
	return doc


def qc_passed(job, finished_good):
	"""Gate used by Packaging Entry and the box-packing scan — Packaging is
	blocked until this returns True. A prior Fail doesn't need any rework
	doctype: QC just re-scans and records a new result, which overwrites
	this same record's status."""
	return (
		frappe.db.get_value("QC Inspection", {"job": job, "finished_good": finished_good}, "status")
		== "Passed"
	)
