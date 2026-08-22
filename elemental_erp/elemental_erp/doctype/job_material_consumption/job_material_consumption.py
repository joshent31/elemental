import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import advance_job_status, assert_active_job


class JobMaterialConsumption(Document):
	def validate(self):
		assert_active_job(self.job)
		for row in self.items:
			consumed = float(row.actual_consumed_qty or 0)
			issued = float(row.total_issued_qty or 0)
			if consumed < 0 or consumed > issued + 1e-6:
				frappe.throw(
					f"Actual Consumed Qty for {row.raw_material} must be between zero and {issued}."
				)
			row.variance_qty = (row.total_issued_qty or 0) - (row.actual_consumed_qty or 0)

	def before_submit(self):
		if not self.job:
			return
		if not frappe.db.get_value("Job", self.job, "packaging_completed"):
			frappe.throw(
				"Cannot confirm material consumption — Packaging has not confirmed this "
				"Job as fully packed yet."
			)
		self.status = "Confirmed"
		self.confirmed_by = frappe.session.user
		self.confirmed_on = frappe.utils.now_datetime()

	def on_submit(self):
		# flip every Material Issue for this Job to Consumed in one shot —
		# this is the "whole job material consumes at once" requirement
		issue_names = frappe.get_all("Material Issue", {"job": self.job, "docstatus": 1}, pluck="name")
		for name in issue_names:
			frappe.db.set_value("Material Issue", name, "status", "Consumed")

		advance_job_status(self.job, "Material Consumed")

	def on_cancel(self):
		issue_names = frappe.get_all("Material Issue", {"job": self.job, "docstatus": 1}, pluck="name")
		for name in issue_names:
			frappe.db.set_value("Material Issue", name, "status", "Issued")
		if frappe.db.get_value("Job", self.job, "status") not in ("Closed", "Cancelled"):
			frappe.db.set_value("Job", self.job, "status", "Material Consumption Pending")


def generate_for_job(job):
	"""Roll up every submitted Material Issue for this Job (across every
	department) into one Draft Job Material Consumption doc, grouped by raw
	material. actual_consumed_qty defaults to the issued qty — the costing
	team edits it down to what was really used before confirming."""
	rows = frappe.db.sql(
		"""
		SELECT mii.raw_material, mii.uom,
		       SUM(mii.issued_qty - COALESCE(mii.returned_qty, 0)) AS total_issued_qty
		FROM `tabMaterial Issue Item` mii
		INNER JOIN `tabMaterial Issue` mi ON mi.name = mii.parent
		WHERE mi.job = %s AND mi.docstatus = 1
		GROUP BY mii.raw_material, mii.uom
		""",
		job,
		as_dict=True,
	)
	if not rows:
		frappe.throw("No submitted Material Issues exist for this Job.")

	existing = frappe.db.get_value(
		"Job Material Consumption", {"job": job, "docstatus": ["<", 2]}, "name"
	)
	if existing:
		doc = frappe.get_doc("Job Material Consumption", existing)
		if doc.docstatus == 1:
			return doc
		doc.set("items", [])
		for row in rows:
			doc.append("items", {
				"raw_material": row.raw_material,
				"uom": row.uom,
				"total_issued_qty": row.total_issued_qty,
				"actual_consumed_qty": row.total_issued_qty,
			})
		doc.save(ignore_permissions=True)
		return doc

	doc = frappe.get_doc(
		{
			"doctype": "Job Material Consumption",
			"job": job,
			"status": "Draft",
			"items": [
				{
					"raw_material": r.raw_material,
					"uom": r.uom,
					"total_issued_qty": r.total_issued_qty,
					"actual_consumed_qty": r.total_issued_qty,  # default; costing team adjusts down
				}
				for r in rows
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc
