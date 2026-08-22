"""Pure helpers for the Purchase Order initiation workbench."""

import math


QUANTITY_TOLERANCE = 1e-9


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
