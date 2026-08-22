import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import assert_active_job


class QCInspection(Document):
	def validate(self):
		assert_active_job(self.job)


def qc_passed(job, finished_good):
	"""Gate used by Packaging Entry and the box-packing scan — Packaging is
	blocked until this returns True. A prior Fail doesn't need any rework
	doctype: QC just re-scans and records a new result, which overwrites
	this same record's status."""
	return (
		frappe.db.get_value("QC Inspection", {"job": job, "finished_good": finished_good}, "status")
		== "Passed"
	)
