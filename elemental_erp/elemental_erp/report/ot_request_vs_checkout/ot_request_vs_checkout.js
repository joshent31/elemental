var elementalMonths = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	.map((label, index) => ({ label, value: String(index + 1) }));

frappe.query_reports["OT Request vs Checkout"] = {
	filters: [
		{ fieldname: "month", label: "Month", fieldtype: "Select", options: elementalMonths, default: String(new Date().getMonth() + 1), reqd: 1 },
		{ fieldname: "year", label: "Year", fieldtype: "Int", default: new Date().getFullYear(), reqd: 1 },
		{ fieldname: "employee_category", label: "Employee Category", fieldtype: "Select", options: "\nStaff\nWorker", default: "Worker" },
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
