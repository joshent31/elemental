import frappe
from frappe.model.document import Document


class QCInspection(Document):
	pass


def qc_passed(job, finished_good):
	"""Gate used by Packaging Entry and the box-packing scan — Packaging is
	blocked until this returns True. A prior Fail doesn't need any rework
	doctype: QC just re-scans and records a new result, which overwrites
	this same record's status."""
	return (
		frappe.db.get_value("QC Inspection", {"job": job, "finished_good": finished_good}, "status")
		== "Passed"
	)
