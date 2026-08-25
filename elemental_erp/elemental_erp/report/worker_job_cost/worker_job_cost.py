import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = []
	values = {}
	for fieldname in ("job", "employee", "workstation", "status"):
		if filters.get(fieldname):
			conditions.append(f"w.{fieldname} = %({fieldname})s")
			values[fieldname] = filters[fieldname]
	if filters.get("from_date"):
		conditions.append("w.work_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("w.work_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	where = " AND ".join(conditions) or "1=1"
	data = frappe.db.sql(
		f"""
		SELECT w.name, w.work_date, w.employee, w.employee_name, w.job,
		       j.job_name, w.workstation, w.department, w.start_time, w.end_time,
		       w.status, w.hourly_rate,
		       CASE WHEN w.status = 'Active'
		            THEN ROUND(TIMESTAMPDIFF(SECOND, w.start_time, NOW()) / 3600, 4)
		            ELSE w.hours_spent END AS hours_spent,
		       CASE WHEN w.status = 'Active'
		            THEN ROUND((TIMESTAMPDIFF(SECOND, w.start_time, NOW()) / 3600) * w.hourly_rate, 2)
		            ELSE w.labour_cost END AS labour_cost,
		       w.started_by, w.closed_by, w.remarks
		FROM `tabWorker Job Time Log` w
		INNER JOIN `tabJob` j ON j.name = w.job
		WHERE {where}
		ORDER BY w.work_date DESC, w.start_time DESC
		""",
		values,
		as_dict=True,
	)
	return get_columns(), data


def get_columns():
	return [
		{"label":"Log","fieldname":"name","fieldtype":"Link","options":"Worker Job Time Log","width":130},
		{"label":"Date","fieldname":"work_date","fieldtype":"Date","width":95},
		{"label":"Worker","fieldname":"employee","fieldtype":"Link","options":"Employee","width":120},
		{"label":"Worker Name","fieldname":"employee_name","fieldtype":"Data","width":150},
		{"label":"Job","fieldname":"job","fieldtype":"Link","options":"Job","width":125},
		{"label":"Job Name","fieldname":"job_name","fieldtype":"Data","width":160},
		{"label":"Machine / Table","fieldname":"workstation","fieldtype":"Link","options":"Production Workstation","width":130},
		{"label":"Department","fieldname":"department","fieldtype":"Link","options":"Department","width":120},
		{"label":"Start","fieldname":"start_time","fieldtype":"Datetime","width":145},
		{"label":"End","fieldname":"end_time","fieldtype":"Datetime","width":145},
		{"label":"Status","fieldname":"status","fieldtype":"Data","width":115},
		{"label":"Hours","fieldname":"hours_spent","fieldtype":"Float","precision":4,"width":85},
		{"label":"Hourly Rate","fieldname":"hourly_rate","fieldtype":"Currency","width":110},
		{"label":"Labour Cost","fieldname":"labour_cost","fieldtype":"Currency","width":115},
		{"label":"Started By","fieldname":"started_by","fieldtype":"Link","options":"User","width":150},
		{"label":"Closed By","fieldname":"closed_by","fieldtype":"Link","options":"User","width":150},
		{"label":"Remarks","fieldname":"remarks","fieldtype":"Data","width":200},
	]
