frappe.query_reports["OT Request vs Checkout"] = {
	filters: [
		{ fieldname: "from_date", label: "From Date", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -7), reqd: 1 },
		{ fieldname: "to_date", label: "To Date", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "department", label: "Department", fieldtype: "Link", options: "Department" },
		{ fieldname: "employee", label: "Employee", fieldtype: "Link", options: "Employee" },
		{ fieldname: "request_status", label: "Request Status", fieldtype: "Select", options: "\nSent to HR\nApproved\nRejected" },
		{ fieldname: "exceptions_only", label: "Exceptions Only", fieldtype: "Check", default: 1 },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "reconciliation" && data) {
			const colors = { Matched: "green", "Unauthorized OT": "red", "Rejected OT Worked": "red", "Excess OT": "orange", "HR Approval Pending": "blue" };
			if (colors[data.reconciliation]) value = `<span style="color:${colors[data.reconciliation]};font-weight:600">${value}</span>`;
		}
		return value;
	},
};
