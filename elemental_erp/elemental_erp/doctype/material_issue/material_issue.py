import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import (
	advance_job_status,
	assert_active_job,
	positive_quantity,
	resolve_department,
)


class MaterialIssue(Document):
	def validate(self):
		assert_active_job(self.job)
		if not self.material_indent:
			frappe.throw("Material Issue must be linked to an approved Material Indent.")
		indent = frappe.db.get_value(
			"Material Indent",
			self.material_indent,
			["name", "job", "department", "docstatus"],
			as_dict=True,
		)
		if not indent or indent.docstatus != 1:
			frappe.throw("Material Issue requires a submitted Material Indent.")
		if indent.job != self.job:
			frappe.throw(
				f"Material Issue Job {self.job} does not match {self.material_indent}, "
				f"which belongs to Job {indent.job}."
			)
		indent_department = resolve_department(indent.department)
		issue_department = resolve_department(self.department)
		if indent_department != issue_department:
			frappe.throw(
				f"Material Issue Department {self.department} does not match "
				f"{self.material_indent} Department {indent.department}."
			)
		# Persist the canonical Link value even when this Issue was populated
		# from an older free-text Material Indent.
		self.department = issue_department

		allowed = {
			r.raw_material: float(r.required_qty or 0)
			for r in frappe.get_all(
				"Material Indent Item",
				filters={"parent": self.material_indent},
				fields=["raw_material", "required_qty"],
			)
		}
		seen = set()
		for row in self.items:
			if row.raw_material in seen:
				frappe.throw(f"Raw Material {row.raw_material} is listed more than once.")
			seen.add(row.raw_material)
			row.issued_qty = positive_quantity(row.issued_qty, f"Issued Qty for {row.raw_material}")
			returned = float(row.returned_qty or 0)
			if returned < 0 or returned > row.issued_qty:
				frappe.throw(f"Returned Qty for {row.raw_material} must be between zero and Issued Qty.")
			if row.raw_material not in allowed:
				frappe.throw(f"Raw Material {row.raw_material} is not present on {self.material_indent}.")
			already_issued = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(mii.issued_qty - COALESCE(mii.returned_qty, 0)), 0)
				FROM `tabMaterial Issue Item` mii
				INNER JOIN `tabMaterial Issue` mi ON mi.name = mii.parent
				WHERE mi.material_indent = %s AND mi.docstatus = 1
				  AND mi.name != %s AND mii.raw_material = %s
				""",
				(self.material_indent, self.name or "", row.raw_material),
			)[0][0] or 0
			if already_issued + row.issued_qty - returned > allowed[row.raw_material] + 1e-6:
				frappe.throw(
					f"Issue quantity for {row.raw_material} exceeds the remaining quantity on "
					f"{self.material_indent}."
				)

	def on_submit(self):
		"""Material now physically lies with the department, against this Job,
		as WIP. It is NOT booked as consumed yet — that only happens in one
		shot for the whole Job, once Packaging confirms completion (see
		Job Material Consumption). This is the "lying in production" state
		the client asked for."""
		advance_job_status(self.job, "In Production")

		# make sure this department shows up in "Departments Closed %" even
		# if it never happens to receive an inter-department transfer —
		# otherwise a department that only draws raw material (typically
		# the first one on a Job) is invisible to that metric.
		from elemental_erp.elemental_erp.doctype.job_department_status.job_department_status import (
			get_or_create,
		)

		get_or_create(self.job, self.department)
