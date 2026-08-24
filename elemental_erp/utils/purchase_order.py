"""Material Indent linkage rules for standard ERPNext Purchase Orders."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from elemental_erp.utils.transactions import advance_job_status


QUANTITY_TOLERANCE = 1e-9


def _linked_indent_names(doc):
	names = set()
	if doc.get("elemental_material_indent"):
		names.add(doc.elemental_material_indent)
	for row in doc.get("items") or []:
		if row.get("elemental_material_indent"):
			names.add(row.elemental_material_indent)
	return names


def _submitted_indent(name, cache):
	if name not in cache:
		indent = frappe.get_doc("Material Indent", name)
		if indent.docstatus != 1:
			frappe.throw(f"Material Indent {name} must be submitted before it can be ordered.")
		cache[name] = indent
	return cache[name]


def validate_material_indent_linkage(doc, method=None):
	"""Link manual PO rows to exact Indent rows and reject over-ordering.

	PO Initiation already supplies exact child-row links. A buyer using the
	standard Purchase Order form only selects the header Material Indent; this
	hook resolves each item to its matching Indent row and applies the same live
	shortfall check used by the workbench.
	"""
	header_indent = doc.get("elemental_material_indent")
	if not header_indent and not any(
		row.get("elemental_material_indent") for row in (doc.get("items") or [])
	):
		return

	indent_cache = {}
	indent_rows = {}
	requested_by_indent_row = defaultdict(float)
	jobs = set()

	for row in doc.get("items") or []:
		indent_name = row.get("elemental_material_indent") or header_indent
		if not indent_name:
			continue
		if header_indent and indent_name != header_indent:
			frappe.throw(
				f"Purchase Order item {row.item_code} is linked to {indent_name}, "
				f"but the Purchase Order header is linked to {header_indent}."
			)

		indent = _submitted_indent(indent_name, indent_cache)
		jobs.add(indent.job)
		row_map = indent_rows.setdefault(
			indent_name,
			{
				child.name: child
				for child in indent.items
			},
		)
		child = row_map.get(row.get("elemental_material_indent_item"))
		if not child:
			matches = [candidate for candidate in indent.items if candidate.raw_material == row.item_code]
			if len(matches) != 1:
				frappe.throw(
					f"Item {row.item_code} does not have one matching row in Material Indent {indent_name}. "
					"Put unrelated items on a separate Purchase Order."
				)
			child = matches[0]
		elif child.raw_material != row.item_code:
			frappe.throw(
				f"Purchase Order item {row.item_code} does not match Material Indent row {child.name}."
			)

		if row.get("uom") and child.uom and row.uom != child.uom:
			frappe.throw(
				f"UOM for {row.item_code} must remain {child.uom} to cross-check it against "
				f"Material Indent {indent_name}."
			)

		row.elemental_material_indent = indent_name
		row.elemental_material_indent_item = child.name
		requested_by_indent_row[(indent_name, child.name, row.item_code)] += flt(row.qty)

	if len(jobs) > 1:
		frappe.throw("One Purchase Order cannot combine Material Indents from different Jobs.")
	if jobs:
		indent_job = next(iter(jobs))
		if doc.get("elemental_job") and doc.elemental_job != indent_job:
			frappe.throw(
				f"Purchase Order Job {doc.elemental_job} does not match Material Indent Job {indent_job}."
			)
		doc.elemental_job = indent_job

	linked_rows = sorted(requested_by_indent_row)
	# Serialize manual and workbench POs against the same source rows. Without
	# this lock, two buyers saving at the same instant could both pass the live
	# balance check before either Purchase Order became visible to the other.
	for indent_name, indent_item, item_code in linked_rows:
		frappe.db.sql(
			"SELECT name FROM `tabMaterial Indent Item` WHERE name = %s FOR UPDATE",
			indent_item,
		)

	for indent_name, indent_item, item_code in linked_rows:
		requested_qty = requested_by_indent_row[(indent_name, indent_item, item_code)]
		child = indent_rows[indent_name][indent_item]
		ordered_elsewhere = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(poi.qty), 0)
			FROM `tabPurchase Order Item` poi
			INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
			WHERE po.docstatus < 2
			  AND po.name != %(purchase_order)s
			  AND poi.item_code = %(item_code)s
			  AND (
				poi.elemental_material_indent_item = %(indent_item)s
				OR (
					COALESCE(poi.elemental_material_indent_item, '') = ''
					AND COALESCE(
						NULLIF(poi.elemental_material_indent, ''),
						po.elemental_material_indent
					) = %(material_indent)s
				)
			  )
			""",
			{
				"purchase_order": doc.name or "",
				"item_code": item_code,
				"indent_item": indent_item,
				"material_indent": indent_name,
			},
		)[0][0] or 0
		remaining = max(flt(child.shortfall_qty) - flt(ordered_elsewhere), 0)
		if requested_qty > remaining + QUANTITY_TOLERANCE:
			frappe.throw(
				f"Only {remaining:g} {child.uom or ''} of {item_code} remains to order "
				f"against Material Indent {indent_name}; this Purchase Order requests {requested_qty:g}."
			)


def mark_material_indents_in_purchase(doc, method=None):
	"""Mark linked submitted Indents only after Purchase actually saves a PO."""
	indent_names = _linked_indent_names(doc)
	for indent_name in indent_names:
		updates = {"status": "Sent to Purchase"}
		if not frappe.db.get_value("Material Indent", indent_name, "purchase_order"):
			updates["purchase_order"] = doc.name
		frappe.db.set_value("Material Indent", indent_name, updates, update_modified=False)
	for job in {
		frappe.db.get_value("Material Indent", indent_name, "job")
		for indent_name in indent_names
	}:
		if job:
			advance_job_status(job, "In Purchase")


def refresh_material_indent_purchase_status(doc, method=None):
	"""Restore an Indent to Approved when its last active linked PO is removed."""
	for indent_name in _linked_indent_names(doc):
		active_po = frappe.db.sql(
			"""
			SELECT DISTINCT po.name
			FROM `tabPurchase Order` po
			LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
			WHERE po.docstatus < 2
			  AND po.name != %(purchase_order)s
			  AND (
				po.elemental_material_indent = %(material_indent)s
				OR poi.elemental_material_indent = %(material_indent)s
			  )
			ORDER BY po.creation ASC
			LIMIT 1
			""",
			{"purchase_order": doc.name or "", "material_indent": indent_name},
		)
		current_status = frappe.db.get_value("Material Indent", indent_name, "status")
		updates = {"purchase_order": active_po[0][0] if active_po else None}
		if current_status in ("Approved", "Sent to Purchase"):
			updates["status"] = "Sent to Purchase" if active_po else "Approved"
		frappe.db.set_value("Material Indent", indent_name, updates, update_modified=False)
