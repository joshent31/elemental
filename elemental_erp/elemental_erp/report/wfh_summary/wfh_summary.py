"""WFH Summary — Script Report.

Shows approved Work from Home days for the selected month. Includes
filters for Employee, Department, Month, Year, and Company.
"""
import calendar
import frappe
from frappe.utils import getdate, add_days


def execute(filters=None):
	filters = filters or {}
	year = int(filters.get("year") or getdate().year)
	month = int(filters.get("month") or getdate().month)
	employee = filters.get("employee")
	department = filters.get("department")
	company = filters.get("company")

	columns = get_columns(year, month)
	data = get_data(year, month, employee, department, company)
	chart = get_chart(data, year, month)

	return columns, data, None, chart


def get_columns(year, month):
	"""Build columns for the selected month."""
	columns = [
		{
			"label": "Employee",
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 200,
		},
		{
			"label": "Employee Name",
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Department",
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 150,
		},
	]

	columns.append({
		"label": f"{calendar.month_abbr[month]} {year}",
		"fieldname": "month_days",
		"fieldtype": "Int",
		"width": 100,
	})

	columns.append({
		"label": "Total Days",
		"fieldname": "total_days",
		"fieldtype": "Int",
		"width": 100,
	})

	columns.append({
		"label": "Requests",
		"fieldname": "total_requests",
		"fieldtype": "Int",
		"width": 80,
	})

	return columns


def get_data(year, month, employee_filter=None, department_filter=None, company_filter=None):
	"""Query approved WFH requests and aggregate the selected month."""
	month_start = f"{year}-{month:02d}-01"
	month_end = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"

	conditions = "wfh.docstatus != 2 AND wfh.status = 'Approved'"
	params = {"month_start": month_start, "month_end": month_end}

	if employee_filter:
		conditions += " AND wfh.employee = %(employee)s"
		params["employee"] = employee_filter

	if department_filter:
		conditions += " AND emp.department = %(department)s"
		params["department"] = department_filter

	if company_filter:
		conditions += " AND wfh.company = %(company)s"
		params["company"] = company_filter

	# Get all approved WFH requests with their employee info
	rows = frappe.db.sql(
		f"""
		SELECT
			wfh.employee,
			wfh.employee_name,
			emp.department,
			wfh.from_date,
			wfh.to_date,
			wfh.total_days,
			wfh.name AS request_name
		FROM `tabWork from Home Request` wfh
		INNER JOIN `tabEmployee` emp ON emp.name = wfh.employee
		WHERE {conditions}
		  AND wfh.from_date <= %(month_end)s
		  AND wfh.to_date >= %(month_start)s
		ORDER BY emp.department, wfh.employee_name
		""",
		params,
		as_dict=True,
	)

	# Pivot: one row per employee, monthly counts
	employee_data = {}
	for row in rows:
		key = row.employee
		if key not in employee_data:
			employee_data[key] = {
				"employee": row.employee,
				"employee_name": row.employee_name,
				"department": row.department,
				"month_days": 0,
				"total_days": 0,
				"total_requests": 0,
			}

		# Count days per month that overlap with this WFH request
		_from = getdate(row.from_date)
		_to = getdate(row.to_date)

		current = max(_from, getdate(month_start))
		end = min(_to, getdate(month_end))

		while current <= end:
			employee_data[key]["month_days"] += 1
			current = add_days(current, 1)

		employee_data[key]["total_requests"] += 1

	# Recalculate totals from monthly columns
	for key, emp_row in employee_data.items():
		emp_row["total_days"] = emp_row.get("month_days", 0)

	# Sort by department then employee name
	result = sorted(employee_data.values(), key=lambda x: (x.get("department") or "", x.get("employee_name") or ""))

	return result


def get_chart(data, year, month):
	"""Bar chart: total WFH days per employee for the selected month."""
	if not data:
		return None

	# Top 10 employees by WFH days
	top = sorted(data, key=lambda x: x.get("total_days", 0), reverse=True)[:10]

	return {
		"data": {
			"labels": [d["employee_name"] or d["employee"] for d in top],
			"datasets": [
				{
					"name": "WFH Days",
					"values": [d.get("total_days", 0) for d in top],
				}
			],
		},
		"type": "bar",
		"colors": ["#7b61ff"],
		"barOptions": {"horizontalBars": True},
	}
