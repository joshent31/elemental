var elementalMonths = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	.map((label, index) => ({ label, value: String(index + 1) }));

frappe.query_reports["Job Consumption Report"] = {
	filters: [
		{ fieldname: "month", label: "Month", fieldtype: "Select", options: elementalMonths, default: String(new Date().getMonth() + 1), reqd: 1 },
		{ fieldname: "year", label: "Year", fieldtype: "Int", default: new Date().getFullYear(), reqd: 1 },
		{ fieldname: "job", label: "Job", fieldtype: "Link", options: "Job" },
		{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
	],
};
