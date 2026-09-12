import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


PROCESS_FIELDS = (
	("process_metal", "Metal"),
	("process_wood", "Wood"),
	("process_electrical", "Electrical"),
	("process_powdercoating", "Powdercoating"),
	("process_paint", "Paint"),
	("process_us_assembly", "US Assembly"),
	("process_packing", "Packing"),
)


def calculate_material_qty(basis, conversion_factor, length=0, width=0, height=0, pieces=1):
	"""Convert millimetre-based FG measurements into the Item's stock UOM."""
	basis = (basis or "Manual").strip()
	factor = float(conversion_factor or 0)
	pieces = float(pieces or 0)
	measurements = {
		"Pieces": pieces,
		"Length": float(length or 0) * pieces,
		"Area": float(length or 0) * float(width or 0) * pieces,
		"Volume": float(length or 0) * float(width or 0) * float(height or 0) * pieces,
	}
	if basis == "Manual":
		return None
	if basis not in measurements:
		frappe.throw(f"Unsupported FG Consumption Basis: {basis}")
	if factor <= 0:
		frappe.throw("FG Conversion Divisor must be greater than zero on the raw-material Item.")
	if measurements[basis] <= 0:
		frappe.throw(f"Enter all measurements required for {basis} calculation and a PCS value greater than zero.")
	return round(measurements[basis] / factor, 6)


def selected_processes(row, migrate_legacy=True):
	"""Return checked processes in production order and migrate old pill values."""
	selected = [label for fieldname, label in PROCESS_FIELDS if int(row.get(fieldname) or 0)]
	if not selected and migrate_legacy:
		raw = row.get("processes") or ""
		legacy = raw.split("\n") if "\n" in raw else raw.split(",")
		legacy = {value.strip() for value in legacy if value.strip()}
		if not legacy:
			legacy = {"US Assembly"}
		for fieldname, label in PROCESS_FIELDS:
			setter = getattr(row, "set", None)
			if callable(setter):
				setter(fieldname, 1 if label in legacy else 0)
			else:
				row[fieldname] = 1 if label in legacy else 0
		selected = [label for fieldname, label in PROCESS_FIELDS if int(row.get(fieldname) or 0)]
	return selected


def generate_part_code():
	"""Generate one globally unique subpart code from Frappe's locked series."""
	part_code = make_autoname("PART-.#####")
	while frappe.db.exists("FG Subpart", {"part_code": part_code}):
		part_code = make_autoname("PART-.#####")
	return part_code


class FinishedGood(Document):
	def before_validate(self):
		if self.is_new() and self.fg_code and frappe.db.exists("Finished Good", self.fg_code):
			self.fg_code = None
		if not (self.fg_code or "").strip():
			self.fg_code = make_autoname(self.naming_series or "FG-.#####")

		# Populate before mandatory child-field validation. The browser normally
		# generates this as soon as Add Row is clicked; this is the authoritative
		# fallback for imports, API inserts, and slow/offline clients.
		for row in self.subparts or []:
			if row.get("part_code") and frappe.db.exists("FG Subpart", {"part_code": row.part_code}):
				row.part_code = None
			if not (row.get("part_code") or "").strip():
				row.part_code = generate_part_code()

	def validate(self):
		for row in self.bom_items or []:
			item = frappe.db.get_value(
				"Item", row.raw_material,
				["stock_uom", "elemental_fg_consumption_basis", "elemental_fg_conversion_factor"],
				as_dict=True,
			) or {}
			row.uom = item.get("stock_uom") or row.uom
			row.calculation_basis = item.get("elemental_fg_consumption_basis") or "Manual"
			row.conversion_factor = float(item.get("elemental_fg_conversion_factor") or 1)
			calculated = calculate_material_qty(
				row.calculation_basis, row.conversion_factor, row.length_mm,
				row.width_mm, row.height_mm, row.pieces,
			)
			if calculated is not None:
				row.qty_per_fg = calculated
			if float(row.qty_per_fg or 0) <= 0:
				frappe.throw(f"Raw material {row.raw_material}: Total Qty / FG must be greater than zero.")

		if not self.subparts:
			frappe.msgprint(
				"No subparts added — QR tracking will be generated at the Finished-Good level only.",
				alert=True,
			)
			return

		seen_codes = set()
		for row in self.subparts:
			processes = selected_processes(row, migrate_legacy=False)
			if not processes:
				frappe.throw(f"Select at least one process for subpart {row.get('part_code') or row.idx}.")
			row.process_flow = " → ".join(processes)
			row.processes = "\n".join(processes)
			part_code = (row.get("part_code") or "").strip()
			if part_code in seen_codes:
				frappe.throw(f"Subpart code {part_code} is listed more than once in this Finished Good.")
			seen_codes.add(part_code)
			if float(row.get("qty_per_fg") or 0) <= 0:
				frappe.throw(f"Qty per FG must be greater than zero for subpart {part_code}.")


@frappe.whitelist()
def get_next_part_code():
	"""Return a reserved code immediately when the user adds a child row."""
	if not (
		frappe.has_permission("Finished Good", ptype="create")
		or frappe.has_permission("Finished Good", ptype="write")
	):
		frappe.throw("You do not have permission to edit Finished Goods.", frappe.PermissionError)
	return generate_part_code()
