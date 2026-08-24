import frappe
from frappe.model.document import Document

from elemental_erp.utils.transactions import advance_job_status, assert_active_job, positive_quantity


class MaterialIndent(Document):
	def validate(self):
		"""Stock check that reflects what's ACTUALLY free for this Job —
		total Bin qty minus whatever other still-open Jobs have already
		claimed on their own submitted Indents. Without this, two Jobs can
		both be told the same units are "available"."""
		assert_active_job(self.job)
		seen = set()
		for row in self.items:
			if row.raw_material in seen:
				frappe.throw(f"Raw Material {row.raw_material} is listed more than once.")
			seen.add(row.raw_material)
			row.required_qty = positive_quantity(row.required_qty, f"Required Qty for {row.raw_material}")

			# Bin is one row per Item/Warehouse. Aggregate all warehouses until
			# the transaction schema gains an explicit source warehouse.
			total_bin_qty = frappe.db.sql(
				"SELECT COALESCE(SUM(actual_qty), 0) FROM `tabBin` WHERE item_code = %s",
				row.raw_material,
			)[0][0] or 0

			reserved_elsewhere = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(GREATEST(mii.required_qty - COALESCE(mii.shortfall_qty, 0), 0)), 0)
				FROM `tabMaterial Indent Item` mii
				INNER JOIN `tabMaterial Indent` mi ON mi.name = mii.parent
				INNER JOIN `tabJob` j ON j.name = mi.job
				WHERE mii.raw_material = %s
				  AND mi.docstatus = 1
				  AND mi.name != %s
				  AND j.status NOT IN ('Closed', 'Cancelled')
				""",
				(row.raw_material, self.name or ""),
			)[0][0] or 0

			row.total_bin_qty = total_bin_qty
			row.reserved_other_jobs = reserved_elsewhere
			row.available_qty = max(total_bin_qty - reserved_elsewhere, 0)
			row.shortfall_qty = max((row.required_qty or 0) - row.available_qty, 0)
			row.amount = (row.required_qty or 0) * (row.rate or 0)

		self.total_indent_value = sum((row.amount or 0) for row in self.items)

	def on_submit(self):
		self.db_set("status", "Approved", update_modified=False)
		advance_job_status(self.job, "Indent Raised")
		self._mark_covered_fg_items_indented()
		# Submission is Costing's approval boundary only. Purchase decides when,
		# from whom, and for how much to order later through PO Initiation or a
		# normal ERPNext Purchase Order. Never create a Draft PO here.

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

	def on_cancel(self):
		"""Release per-FG indent flags when no other submitted indent covers them."""
		purchase_orders = set()
		if self.purchase_order:
			purchase_orders.add(self.purchase_order)
		purchase_orders.update(
			frappe.get_all(
				"Purchase Order",
				filters={"elemental_material_indent": self.name, "docstatus": ["<", 2]},
				pluck="name",
			)
		)
		purchase_orders.update(
			row[0]
			for row in frappe.db.sql(
				"""
				SELECT DISTINCT poi.parent
				FROM `tabPurchase Order Item` poi
				INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
				WHERE poi.elemental_material_indent = %s
				  AND po.docstatus < 2
				""",
				self.name,
			)
		)
		for purchase_order in purchase_orders:
			if not frappe.db.exists("Purchase Order", purchase_order):
				continue
			po = frappe.get_doc("Purchase Order", purchase_order)
			if po.docstatus == 0:
				frappe.delete_doc("Purchase Order", po.name, ignore_permissions=True)
			elif po.docstatus == 1:
				po.cancel()
		if not self.covered_finished_goods:
			return
		try:
			import json

			fg_codes = set(json.loads(self.covered_finished_goods) or [])
		except Exception:
			return
		covered_elsewhere = set()
		for raw in frappe.get_all(
			"Material Indent",
			filters={"job": self.job, "docstatus": 1, "name": ["!=", self.name]},
			pluck="covered_finished_goods",
		):
			try:
				covered_elsewhere.update(json.loads(raw) or [])
			except Exception:
				continue
		job_doc = frappe.get_doc("Job", self.job)
		for row in job_doc.fg_items:
			if row.finished_good in fg_codes and row.finished_good not in covered_elsewhere:
				row.indent_raised = 0
		job_doc.save(ignore_permissions=True)
