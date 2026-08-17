import frappe
from frappe.model.document import Document


class JobMaterialConsumption(Document):
	def validate(self):
		for row in self.items:
			row.variance_qty = (row.total_issued_qty or 0) - (row.actual_consumed_qty or 0)

	def before_submit(self):
		if not self.job:
			return
		if not frappe.db.get_value("Job", self.job, "packaging_completed"):
			frappe.throw(
				"Cannot confirm material consumption — Packaging has not confirmed this "
				"Job as fully packed yet."
			)

	def on_submit(self):
		self.status = "Confirmed"
		self.confirmed_by = frappe.session.user
		self.confirmed_on = frappe.utils.now_datetime()

		# flip every Material Issue for this Job to Consumed in one shot —
		# this is the "whole job material consumes at once" requirement
		issue_names = frappe.get_all("Material Issue", {"job": self.job, "docstatus": 1}, pluck="name")
		for name in issue_names:
			frappe.db.set_value("Material Issue", name, "status", "Consumed")

		frappe.db.set_value("Job", self.job, "status", "Material Consumed")


def generate_for_job(job):
	"""Roll up every submitted Material Issue for this Job (across every
	department) into one Draft Job Material Consumption doc, grouped by raw
	material. actual_consumed_qty defaults to the issued qty — the costing
	team edits it down to what was really used before confirming."""
	if frappe.db.exists("Job Material Consumption", {"job": job}):
		return frappe.get_doc("Job Material Consumption", {"job": job})

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
