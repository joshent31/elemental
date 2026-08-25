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
	def validate(self):
		if not self.subparts:
			frappe.msgprint(
				"No subparts added — QR tracking will be generated at the Finished-Good level only.",
				alert=True,
			)
			return

		seen_codes = set()
		for row in self.subparts:
			if not (row.get("part_code") or "").strip():
				row.part_code = generate_part_code()
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
