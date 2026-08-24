"""Material Indent linkage rules for standard ERPNext Purchase Orders."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from elemental_erp.utils.purchase import split_moq_order_quantity
from elemental_erp.utils.transactions import advance_job_status


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


def _minimum_order_qty(item_code, supplier):
	if not supplier:
		frappe.throw("Select a Supplier before linking a Purchase Order to a Material Indent.")
	return flt(
		frappe.db.get_value(
			"Item Supplier Elemental",
			{"parent": item_code, "parenttype": "Item", "supplier": supplier},
			"minimum_order_qty",
		)
		or 0
	)


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
	po_rows_by_indent_row = defaultdict(list)
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
		key = (indent_name, child.name, row.item_code)
		requested_by_indent_row[key] += flt(row.qty)
		po_rows_by_indent_row[key].append(row)

	if len(jobs) > 1 and doc.get("elemental_job"):
		frappe.throw(
			"A Purchase Order linked to multiple Jobs must leave Elemental Job blank; "
			"each item row retains its exact Material Indent and Job allocation."
		)
	if len(jobs) == 1:
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

	remaining_by_indent_row = {}
	for indent_name, indent_item, item_code in linked_rows:
		child = indent_rows[indent_name][indent_item]
		ordered_elsewhere = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(
				CASE
					WHEN COALESCE(poi.elemental_indent_required_qty, 0) > 0
					THEN LEAST(poi.elemental_indent_required_qty, poi.qty)
					ELSE poi.qty
				END
			), 0)
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
		remaining_by_indent_row[(indent_name, indent_item, item_code)] = max(
			flt(child.shortfall_qty) - flt(ordered_elsewhere),
			0,
		)

	requested_by_item = defaultdict(float)
	remaining_by_item = defaultdict(float)
	minimum_by_item = {}
	for key in linked_rows:
		item_code = key[2]
		requested_by_item[item_code] += requested_by_indent_row[key]
		remaining_by_item[item_code] += remaining_by_indent_row[key]
		minimum_by_item[item_code] = _minimum_order_qty(item_code, doc.supplier)

	for item_code, requested_qty in requested_by_item.items():
		try:
			split_moq_order_quantity(
				remaining_by_item[item_code],
				requested_qty,
				minimum_by_item[item_code],
			)
		except ValueError as error:
			frappe.throw(f"{item_code}: {error}")

	for key in linked_rows:
		item_code = key[2]
		coverage_remaining = remaining_by_indent_row[key]
		for row in po_rows_by_indent_row[key]:
			row_qty = flt(row.qty)
			covered_qty = min(row_qty, coverage_remaining)
			row.elemental_indent_required_qty = covered_qty
			row.elemental_moq_qty = minimum_by_item[item_code]
			row.elemental_excess_qty = max(row_qty - covered_qty, 0)
			coverage_remaining = max(coverage_remaining - covered_qty, 0)


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
