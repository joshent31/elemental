import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label":"Lot","fieldname":"name","fieldtype":"Link","options":"Virtual FG Transfer","width":140},
		{"label":"Customer","fieldname":"customer","fieldtype":"Link","options":"Customer","width":140},
		{"label":"Finished Good","fieldname":"finished_good","fieldtype":"Link","options":"Finished Good","width":130},
		{"label":"Source Job","fieldname":"source_job","fieldtype":"Link","options":"Job","width":140},
		{"label":"Location","fieldname":"intended_location","fieldtype":"Data","width":130},
		{"label":"Transferred","fieldname":"qty","fieldtype":"Float","width":100},
		{"label":"Reserved","fieldname":"reserved_qty","fieldtype":"Float","width":90},
		{"label":"Utilized","fieldname":"utilized_qty","fieldtype":"Float","width":90},
		{"label":"Available","fieldname":"available_qty","fieldtype":"Float","width":90},
		{"label":"Status","fieldname":"status","fieldtype":"Data","width":110},
		{"label":"Stock Entry","fieldname":"stock_entry","fieldtype":"Link","options":"Stock Entry","width":140}
	]
	conditions, values = ["t.docstatus=1"], {}
	for field in ("customer","finished_good","source_job","intended_location","status"):
		if filters.get(field): conditions.append(f"t.{field}=%({field})s"); values[field]=filters[field]
	data = frappe.db.sql(f"""SELECT t.*, COALESCE(SUM(CASE WHEN r.docstatus=1 THEN r.reserved_qty ELSE 0 END),0) reserved_qty,
		COALESCE(SUM(CASE WHEN r.docstatus=1 THEN r.utilized_qty ELSE 0 END),0) utilized_qty,
		t.qty-COALESCE(SUM(CASE WHEN r.docstatus=1 THEN r.reserved_qty ELSE 0 END),0) available_qty
		FROM `tabVirtual FG Transfer` t LEFT JOIN `tabVirtual FG Reservation` r ON r.virtual_transfer=t.name
		WHERE {' AND '.join(conditions)} GROUP BY t.name ORDER BY t.creation DESC""", values, as_dict=True)
	chart={"data":{"labels":[r.finished_good for r in data],"datasets":[{"name":"Available","values":[flt(r.available_qty) for r in data]},{"name":"Reserved","values":[flt(r.reserved_qty-r.utilized_qty) for r in data]}]},"type":"bar"}
	return columns, data, None, chart
