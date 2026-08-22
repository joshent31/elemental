import frappe
from frappe.model.document import Document


class MaterialIndent(Document):
	def validate(self):
		"""Stock check that reflects what's ACTUALLY free for this Job —
		total Bin qty minus whatever other still-open Jobs have already
		claimed on their own submitted Indents. Without this, two Jobs can
		both be told the same units are "available"."""
		for row in self.items:
			total_bin_qty = frappe.db.get_value(
				"Bin", {"item_code": row.raw_material}, "actual_qty"
			) or 0

			reserved_elsewhere = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(mii.required_qty), 0)
				FROM `tabMaterial Indent Item` mii
				INNER JOIN `tabMaterial Indent` mi ON mi.name = mii.parent
				INNER JOIN `tabJob` j ON j.name = mi.job
				WHERE mii.raw_material = %s
				  AND mi.docstatus = 1
				  AND mi.job != %s
				  AND j.status NOT IN ('Closed', 'Cancelled')
				""",
				(row.raw_material, self.job or ""),
			)[0][0] or 0

			row.total_bin_qty = total_bin_qty
			row.reserved_other_jobs = reserved_elsewhere
			row.available_qty = max(total_bin_qty - reserved_elsewhere, 0)
			row.shortfall_qty = max((row.required_qty or 0) - row.available_qty, 0)
			row.amount = (row.required_qty or 0) * (row.rate or 0)

		self.total_indent_value = sum((row.amount or 0) for row in self.items)

	def on_submit(self):
		self.status = "Approved"
		frappe.db.set_value("Job", self.job, "status", "Indent Raised")
		self._mark_covered_fg_items_indented()

		# "once approved, it goes to Purchase Order in draft" — auto-create
		# immediately if a supplier can be resolved from the Item's default
		# supplier table. If no supplier is configured, skip auto-PO and
		# let the user create one manually via the "Create Purchase Order"
		# button.
		from elemental_erp.api import _create_po_from_indent_doc

		po = _create_po_from_indent_doc(self)
		if po:
			frappe.msgprint(
				f"Shortfall detected \u2014 Draft Purchase Order {po.name} created automatically.",
				alert=True,
			)
		else:
			shortfall_count = sum(1 for r in self.items if (r.shortfall_qty or 0) > 0)
			if shortfall_count:
				frappe.msgprint(
					"Shortfall detected but no default supplier configured on the items. "
					"Please create the Purchase Order manually.",
					alert=True,
				)

	def _mark_covered_fg_items_indented(self):
		"""If this Indent was built via "Pull Items from Job BOM", flag the
		Job FG Item rows it covered as indent_raised — so the next BOM pull
		for this Job only includes items that genuinely haven't been
		indented yet, instead of re-totaling everything from scratch."""
		if not self.covered_finished_goods:
			return
		try:
			import json

			fg_codes = json.loads(self.covered_finished_goods)
		except Exception:
			return
		if not fg_codes:
			return

		job_doc = frappe.get_doc("Job", self.job)
		changed = False
		for row in job_doc.fg_items:
			if row.finished_good in fg_codes and not row.indent_raised:
				row.indent_raised = 1
				changed = True
		if changed:
			job_doc.save(ignore_permissions=True)
