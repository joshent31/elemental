"""Pure helpers for the Purchase Order initiation workbench."""

import math


QUANTITY_TOLERANCE = 1e-9


def split_moq_order_quantity(required_qty, po_qty, minimum_order_qty=0):
	"""Split a PO quantity into its Indent-covered and MOQ-excess portions.

	Buying above the outstanding requirement is allowed only when the selected
	supplier's MOQ is itself above that requirement. The unavoidable excess is
	therefore free stock for future Jobs, not extra consumption by this Job.
	"""
	required_qty = float(required_qty)
	po_qty = float(po_qty)
	minimum_order_qty = float(minimum_order_qty or 0)
	if not math.isfinite(required_qty) or required_qty <= QUANTITY_TOLERANCE:
		raise ValueError("There is no outstanding Indent quantity to purchase.")
	if not math.isfinite(po_qty) or po_qty <= QUANTITY_TOLERANCE:
		raise ValueError("PO quantity must be a finite number greater than zero.")
	if not math.isfinite(minimum_order_qty) or minimum_order_qty < 0:
		raise ValueError("Minimum Order Qty must be a finite non-negative number.")
	if minimum_order_qty > QUANTITY_TOLERANCE and po_qty + QUANTITY_TOLERANCE < minimum_order_qty:
		raise ValueError(
			f"PO quantity must be at least the supplier MOQ of {minimum_order_qty:g}."
		)
	if po_qty > required_qty + QUANTITY_TOLERANCE and not (
		minimum_order_qty > required_qty + QUANTITY_TOLERANCE
		and po_qty + QUANTITY_TOLERANCE >= minimum_order_qty
	):
		raise ValueError(
			f"Only {required_qty:g} is outstanding. A higher PO quantity is allowed only "
			"when the selected supplier's MOQ is above the outstanding requirement."
		)
	return {
		"indent_qty": min(po_qty, required_qty),
		"excess_qty": max(po_qty - required_qty, 0),
	}


def allocate_order_quantity(outstanding_rows, requested_qty):
	"""Allocate a requested quantity across oldest outstanding indent rows.

	The caller is responsible for ordering ``outstanding_rows`` and locking the
	database rows.  This helper stays framework-free so the allocation rules can
	be regression-tested without a Frappe site.
	"""
	requested_qty = float(requested_qty)
	if not math.isfinite(requested_qty) or requested_qty <= 0:
		raise ValueError("PO quantity must be a finite number greater than zero.")

	remaining = requested_qty
	allocations = []
	for source in outstanding_rows:
		available = float(source.get("bal_indent_qty") or 0)
		if not math.isfinite(available) or available <= QUANTITY_TOLERANCE:
			continue
		allocated = min(available, remaining)
		allocation = dict(source)
		allocation["po_qty"] = allocated
		allocations.append(allocation)
		remaining -= allocated
		if remaining <= QUANTITY_TOLERANCE:
			break

	if remaining > QUANTITY_TOLERANCE:
		available = requested_qty - remaining
		raise ValueError(
			f"Only {available:g} is still outstanding; requested {requested_qty:g}. Refresh and try again."
		)
	return allocations
