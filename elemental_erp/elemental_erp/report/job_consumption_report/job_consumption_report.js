frappe.query_reports["Job Consumption Report"] = {
	filters: [
		{ fieldname: "month", label: "Month", fieldtype: "Select", options: "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12", default: String(new Date().getMonth() + 1), reqd: 1 },
		{ fieldname: "year", label: "Year", fieldtype: "Int", default: new Date().getFullYear(), reqd: 1 },
		{ fieldname: "job", label: "Job", fieldtype: "Link", options: "Job" },
		{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
	],
};
