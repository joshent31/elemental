var elementalMonths = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	.map((label, index) => ({ label, value: String(index + 1) }));

frappe.query_reports["Worker Attendance Report"] = {
	filters: [
		{ fieldname: "month", label: "Month", fieldtype: "Select", options: elementalMonths, default: String(new Date().getMonth() + 1), reqd: 1 },
		{ fieldname: "year", label: "Year", fieldtype: "Int", default: new Date().getFullYear(), reqd: 1 },
		{ fieldname: "employee_category", label: "Employee Category", fieldtype: "Select", options: "\nStaff\nWorker", default: "Worker" },
		{ fieldname: "department", label: "Department", fieldtype: "Link", options: "Department" },
	],
};
