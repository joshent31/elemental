import frappe
from frappe.model.document import Document


class MaterialIssue(Document):
	def on_submit(self):
		"""Material now physically lies with the department, against this Job,
		as WIP. It is NOT booked as consumed yet — that only happens in one
		shot for the whole Job, once Packaging confirms completion (see
		Job Material Consumption). This is the "lying in production" state
		the client asked for."""
		frappe.db.set_value("Job", self.job, "status", "In Production")

		# make sure this department shows up in "Departments Closed %" even
		# if it never happens to receive an inter-department transfer —
		# otherwise a department that only draws raw material (typically
		# the first one on a Job) is invisible to that metric.
		from elemental_erp.elemental_erp.doctype.job_department_status.job_department_status import (
			get_or_create,
		)

		get_or_create(self.job, self.department)
