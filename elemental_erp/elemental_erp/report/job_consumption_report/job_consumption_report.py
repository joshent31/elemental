import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	has_sales_invoice_job = frappe.db.has_column("Sales Invoice", "elemental_job")
	data = get_data(filters, has_sales_invoice_job=has_sales_invoice_job)
	chart = get_chart(data)
	message = None
	if not has_sales_invoice_job:
		message = (
			"Sales Invoice job linkage is not installed on this site. "
			"Run bench migrate to create the elemental_job custom field; "
			"profitability is unavailable until then."
		)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": "Job", "fieldname": "job", "fieldtype": "Link", "options": "Job", "width": 120},
		{"label": "Job Name", "fieldname": "job_name", "fieldtype": "Data", "width": 150},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 140},
		{"label": "Indent Qty", "fieldname": "indent_qty", "fieldtype": "Float", "width": 90},
		{"label": "Indent Value \u2014 Costing (BOM)", "fieldname": "indent_value_costing", "fieldtype": "Currency", "width": 160},
		{"label": "Indent Value \u2014 Dept. Requests", "fieldname": "indent_value_dept", "fieldtype": "Currency", "width": 170},
		{"label": "Total Indent Value", "fieldname": "total_indent_value", "fieldtype": "Currency", "width": 140},
		{"label": "Material Issued (WIP)", "fieldname": "issued_qty", "fieldtype": "Float", "width": 130},
		{"label": "Material Actually Consumed", "fieldname": "consumed_qty", "fieldtype": "Float", "width": 160},
		{"label": "Consumption Status", "fieldname": "consumption_status", "fieldtype": "Data", "width": 150},
		{"label": "Available Stock (indented items)", "fieldname": "available_qty", "fieldtype": "Float", "width": 170},
		{"label": "Shortfall to Purchase", "fieldname": "shortfall_qty", "fieldtype": "Float", "width": 140},
		{"label": "QR Completion %", "fieldname": "qr_pct", "fieldtype": "Percent", "width": 120},
		{"label": "Departments Closed %", "fieldname": "dept_pct", "fieldtype": "Percent", "width": 130},
		{"label": "Boxes Installed %", "fieldname": "box_pct", "fieldtype": "Percent", "width": 120},
		{"label": "Design Hours / Cost", "fieldname": "design_summary", "fieldtype": "Data", "width": 150},
		{"label": "Data Entry Hours / Cost", "fieldname": "data_entry_summary", "fieldtype": "Data", "width": 160},
		{"label": "Production Hours / Cost", "fieldname": "production_summary", "fieldtype": "Data", "width": 160},
		{"label": "Scanned Worker Hours / Cost", "fieldname": "worker_job_summary", "fieldtype": "Data", "width": 185},
		{"label": "Packaging Hours / Cost", "fieldname": "packaging_summary", "fieldtype": "Data", "width": 160},
		{"label": "Dispatch Hours / Cost", "fieldname": "dispatch_summary", "fieldtype": "Data", "width": 150},
		{"label": "Total Manpower Cost", "fieldname": "total_manpower_cost", "fieldtype": "Currency", "width": 150},
		{"label": "Total Cost (Material + Manpower)", "fieldname": "total_cost", "fieldtype": "Currency", "width": 190},
		{"label": "Sales Invoice Value", "fieldname": "sales_invoice_value", "fieldtype": "Currency", "width": 140},
		{"label": "Profit / Loss", "fieldname": "profit", "fieldtype": "Currency", "width": 120},
		{"label": "Margin %", "fieldname": "margin_pct", "fieldtype": "Percent", "width": 100},
		{"label": "Profitable?", "fieldname": "profitable", "fieldtype": "Data", "width": 110},
	]


def _pct(done, total):
	if not total:
		return 0
	return round((done / total) * 100, 1)


def get_data(filters, has_sales_invoice_job=None):
	if has_sales_invoice_job is None:
		has_sales_invoice_job = frappe.db.has_column("Sales Invoice", "elemental_job")

	conditions = ""
	if filters.get("job"):
		conditions += " AND j.name = %(job)s"
	if filters.get("customer"):
		conditions += " AND j.customer = %(customer)s"
	if filters.get("year"):
		conditions += " AND YEAR(j.creation) = %(year)s"
		filters["year"] = int(filters["year"])
	if filters.get("month"):
		conditions += " AND MONTH(j.creation) = %(month)s"
		filters["month"] = int(filters["month"])

	jobs = frappe.db.sql(
		f"""
		SELECT j.name AS job, j.job_name, j.customer, j.status
		FROM `tabJob` j
		WHERE j.status != 'Cancelled' {conditions}
		ORDER BY j.creation DESC
		""",
		filters,
		as_dict=True,
	)

	data = []
	for job in jobs:
		# Indent qty, available stock, shortfall — across ALL indents for
		# this Job regardless of who raised them (Costing's BOM pull, or a
		# department like Packaging/Paints raising its own request)
		indent = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(mii.required_qty), 0) AS indent_qty,
			       COALESCE(SUM(mii.available_qty), 0) AS available_qty,
			       COALESCE(SUM(mii.shortfall_qty), 0) AS shortfall_qty
			FROM `tabMaterial Indent Item` mii
			INNER JOIN `tabMaterial Indent` mi ON mi.name = mii.parent
			WHERE mi.job = %s AND mi.docstatus = 1
			""",
			job.job,
			as_dict=True,
		)[0]

		# Indent VALUE, split by who raised it — Costing's BOM-driven indent
		# vs any department (Packaging, Paints, etc.) raising its own
		# request for items outside the BOM. Both roll up into one total.
		indent_value_rows = frappe.db.sql(
			"""
			SELECT mi.raised_by, COALESCE(SUM(mi.total_indent_value), 0) AS value
			FROM `tabMaterial Indent` mi
			WHERE mi.job = %s AND mi.docstatus = 1
			GROUP BY mi.raised_by
			""",
			job.job,
			as_dict=True,
		)
		indent_value_costing = sum(r.value for r in indent_value_rows if r.raised_by == "Costing (BOM)")
		indent_value_dept = sum(r.value for r in indent_value_rows if r.raised_by != "Costing (BOM)")
		total_indent_value = indent_value_costing + indent_value_dept

		# Material Issued (WIP) — lying with departments, not yet booked
		issued_qty = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(mii.issued_qty - COALESCE(mii.returned_qty, 0)), 0) AS q
			FROM `tabMaterial Issue Item` mii
			INNER JOIN `tabMaterial Issue` mi ON mi.name = mii.parent
			WHERE mi.job = %s AND mi.docstatus = 1
			""",
			job.job,
		)[0][0]

		# Material ACTUALLY consumed — only booked once Packaging confirms
		# completion and Costing confirms the Job Material Consumption doc.
		# This intentionally does NOT equal the full indent/issue qty.
		consumption = frappe.db.get_value(
			"Job Material Consumption", {"job": job.job}, ["status"], as_dict=True
		)
		consumed_qty = 0
		consumption_status = "Not Started"
		if consumption:
			consumption_status = consumption.status
			consumed_qty = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(actual_consumed_qty), 0) AS q
				FROM `tabJob Material Consumption Item` jmci
				INNER JOIN `tabJob Material Consumption` jmc ON jmc.name = jmci.parent
				WHERE jmc.job = %s
				""",
				job.job,
			)[0][0]
			if consumption_status != "Confirmed":
				consumption_status = "Draft (pending costing review)"

		# --- Manpower: Design ---
		design = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours, COALESCE(SUM(design_cost), 0) AS cost
			FROM `tabDesign Task` WHERE job = %s
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Manpower: Data Entry ---
		data_entry = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours, COALESCE(SUM(data_entry_cost), 0) AS cost
			FROM `tabData Entry Task` WHERE job = %s
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Manpower: Production ---
		production = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours, COALESCE(SUM(production_cost), 0) AS cost
			FROM `tabProduction Entry` WHERE job = %s AND docstatus = 1
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Manpower: supervisor-scanned worker-to-Job time segments ---
		worker_job = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours,
			       COALESCE(SUM(labour_cost), 0) AS cost
			FROM `tabWorker Job Time Log`
			WHERE job = %s AND status != 'Active'
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Manpower: Packaging ---
		packaging = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours, COALESCE(SUM(packaging_cost), 0) AS cost
			FROM `tabPackaging Entry` WHERE job = %s AND docstatus = 1
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Manpower: Dispatch ---
		dispatch = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(hours_spent), 0) AS hours, COALESCE(SUM(dispatch_cost), 0) AS cost
			FROM `tabDispatch Entry` WHERE job = %s AND docstatus = 1
			""",
			job.job,
			as_dict=True,
		)[0]

		total_manpower_cost = (
			(design.cost or 0) + (data_entry.cost or 0) + (production.cost or 0)
			+ (worker_job.cost or 0) + (packaging.cost or 0) + (dispatch.cost or 0)
		)

		# --- Completion percentages ---
		qr_totals = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(completed_qty), 0) AS done, COALESCE(SUM(total_qty), 0) AS total
			FROM `tabQR Code Master` WHERE job = %s
			""",
			job.job,
			as_dict=True,
		)[0]

		dept_totals = frappe.db.sql(
			"""
			SELECT COUNT(*) AS total,
			       SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) AS closed
			FROM `tabJob Department Status` WHERE job = %s
			""",
			job.job,
			as_dict=True,
		)[0]

		box_totals = frappe.db.sql(
			"""
			SELECT COUNT(*) AS total,
			       SUM(CASE WHEN status = 'Installed' THEN 1 ELSE 0 END) AS installed
			FROM `tabPacking Box` WHERE job = %s
			""",
			job.job,
			as_dict=True,
		)[0]

		# --- Profitability: Sales Invoice value vs. total cost so far ---
		# Includes Draft invoices (not just submitted) since the point is an
		# early profitability signal, not final accounting — cancelled
		# invoices are excluded.
		if has_sales_invoice_job:
			sales_invoice_value = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(grand_total), 0)
				FROM `tabSales Invoice`
				WHERE `elemental_job` = %s AND docstatus != 2
				""",
				job.job,
			)[0][0] or 0
		else:
			sales_invoice_value = 0

		total_cost = total_indent_value + total_manpower_cost
		profit = sales_invoice_value - total_cost if sales_invoice_value else 0
		margin_pct = round((profit / sales_invoice_value) * 100, 1) if sales_invoice_value else 0

		if not has_sales_invoice_job:
			profitable = "Setup Required"
		elif not sales_invoice_value:
			profitable = "Pending Invoice"
		elif profit > 0:
			profitable = "Yes"
		elif profit == 0:
			profitable = "Break-even"
		else:
			profitable = "No"

		data.append(
			{
				"job": job.job,
				"job_name": job.job_name,
				"customer": job.customer,
				"status": job.status,
				"indent_qty": indent.indent_qty,
				"indent_value_costing": indent_value_costing,
				"indent_value_dept": indent_value_dept,
				"total_indent_value": total_indent_value,
				"issued_qty": issued_qty,
				"consumed_qty": consumed_qty,
				"consumption_status": consumption_status,
				"available_qty": indent.available_qty,
				"shortfall_qty": indent.shortfall_qty,
				"qr_pct": _pct(qr_totals.done, qr_totals.total),
				"dept_pct": _pct(dept_totals.closed or 0, dept_totals.total or 0),
				"box_pct": _pct(box_totals.installed or 0, box_totals.total or 0),
				"design_summary": f"{design.hours or 0}h / {design.cost or 0}",
				"data_entry_summary": f"{data_entry.hours or 0}h / {data_entry.cost or 0}",
				"production_summary": f"{production.hours or 0}h / {production.cost or 0}",
				"worker_job_summary": f"{worker_job.hours or 0}h / {worker_job.cost or 0}",
				"packaging_summary": f"{packaging.hours or 0}h / {packaging.cost or 0}",
				"dispatch_summary": f"{dispatch.hours or 0}h / {dispatch.cost or 0}",
				"total_manpower_cost": total_manpower_cost,
				"total_cost": total_cost,
				"sales_invoice_value": sales_invoice_value,
				"profit": profit,
				"margin_pct": margin_pct,
				"profitable": profitable,
			}
		)

	return data


def get_chart(data):
	if not data:
		return None
	rows = data[:12]
	return {
		"data": {
			"labels": [row.get("job") for row in rows],
			"datasets": [
				{"name": "Revenue", "values": [row.get("sales_invoice_value") or 0 for row in rows]},
				{"name": "Total Cost", "values": [row.get("total_cost") or 0 for row in rows]},
				{"name": "Profit / Loss", "values": [row.get("profit") or 0 for row in rows]},
			],
		},
		"type": "bar",
		"colors": ["#2e7d32", "#ef6c00", "#1565c0"],
	}
