import frappe
from frappe.utils import add_days, today
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = filters.from_date or add_days(today(), -30)
	filters.to_date = filters.to_date or today()
	columns = [
		{"label":"Changed On","fieldname":"changed_on","fieldtype":"Datetime","width":150},
		{"label":"Job","fieldname":"job","fieldtype":"Link","options":"Job","width":140},
		{"label":"Customer","fieldname":"customer","fieldtype":"Link","options":"Customer","width":140},
		{"label":"Finished Good","fieldname":"finished_good","fieldtype":"Link","options":"Finished Good","width":130},
		{"label":"Original Qty","fieldname":"original_qty","fieldtype":"Float","width":100},
		{"label":"New Qty","fieldname":"new_qty","fieldtype":"Float","width":100},
		{"label":"Change (+/-)","fieldname":"change_qty_display","fieldtype":"Data","width":105},
		{"label":"Type","fieldname":"change_type","fieldtype":"Data","width":90},
		{"label":"Changed By","fieldname":"changed_by","fieldtype":"Link","options":"User","width":150},
		{"label":"Reason","fieldname":"reason","fieldtype":"Data","width":220}
	]
	conditions, values = ["DATE(changed_on) BETWEEN %(from_date)s AND %(to_date)s"], {"from_date":filters.from_date,"to_date":filters.to_date}
	for field in ("job","customer","finished_good"):
		if filters.get(field):
			conditions.append(f"{field}=%({field})s"); values[field] = filters[field]
	data = frappe.db.sql(f"SELECT * FROM `tabJob FG Change Log` WHERE {' AND '.join(conditions)} ORDER BY changed_on DESC", values, as_dict=True)
	for row in data:
		row.change_qty_display = f"{flt(row.change_qty):+g}"
	chart = {"data":{"labels":[r.finished_good for r in data[:20]],"datasets":[{"name":"Net Change","values":[flt(r.change_qty) for r in data[:20]]}]},"type":"bar","colors":["#2490ef"]}
	return columns, data, None, chart
