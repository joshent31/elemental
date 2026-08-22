"""WFH Summary — Script Report.

Shows a matrix of employees (rows) × months (columns) with the number
of approved Work from Home days each employee took. Includes filters
for Employee, Department, Year, and Company.
"""
import calendar
import frappe
from frappe.utils import getdate, add_months


def execute(filters=None):
	filters = filters or {}
	year = filters.get("year") or getdate().year
	employee = filters.get("employee")
	department = filters.get("department")
	company = filters.get("company")

	columns = get_columns(year)
	data = get_data(year, employee, department, company)
	chart = get_chart(data, year)

	return columns, data, None, chart


def get_columns(year):
	"""Build month columns for the given year + a Total column."""
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

	for month_num in range(1, 13):
		month_name = calendar.month_abbr[month_num]
		columns.append({
			"label": f"{month_name} {year}",
			"fieldname": f"month_{month_num:02d}",
			"fieldtype": "Int",
			"width": 90,
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


def get_data(year, employee_filter=None, department_filter=None, company_filter=None):
	"""Query approved WFH requests for the given year and pivot into
	one row per employee with monthly day counts."""
	year_start = f"{year}-01-01"
	year_end = f"{year}-12-31"

	conditions = "wfh.docstatus != 2 AND wfh.status = 'Approved'"
	params = {"year_start": year_start, "year_end": year_end}

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
		  AND wfh.from_date <= %(year_end)s
		  AND wfh.to_date >= %(year_start)s
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
				"total_days": 0,
				"total_requests": 0,
			}
			# Initialize month columns
			for m in range(1, 13):
				employee_data[key][f"month_{m:02d}"] = 0

		# Count days per month that overlap with this WFH request
	_from = getdate(row.from_date)
	_to = getdate(row.to_date)

	current = max(_from, getdate(year_start))
	end = min(_to, getdate(year_end))

	while current <= end:
		month_key = f"month_{current.month:02d}"
		employee_data[key][month_key] += 1
		current = add_months(current.replace(day=1), 1)
		if current.month == 1 and current.day == 1:
			# We've crossed into next year — shouldn't happen due to filters, but safety
			break
		# Move to next day
		import datetime
		current = current + datetime.timedelta(days=1)
		# Skip to next month if we've passed the end of this month
		if current.day != 1 and current.month != end.month:
			current = current.replace(day=1)
			current = add_months(current, 1)

	employee_data[key]["total_days"] = row.total_days or 0
	employee_data[key]["total_requests"] += 1

	# Recalculate totals from monthly columns
	for key, emp_row in employee_data.items():
		emp_row["total_days"] = sum(
			emp_row.get(f"month_{m:02d}", 0) for m in range(1, 13)
		)

	# Sort by department then employee name
	result = sorted(employee_data.values(), key=lambda x: (x.get("department") or "", x.get("employee_name") or ""))

	return result


def get_chart(data, year):
	"""Bar chart: total WFH days per employee for the year."""
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
