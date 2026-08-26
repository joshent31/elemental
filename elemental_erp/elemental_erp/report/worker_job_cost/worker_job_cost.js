frappe.query_reports["Worker Job Cost"] = {
	filters: [
		{ fieldname: "month", label: "Month", fieldtype: "Select", options: "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12", default: String(new Date().getMonth() + 1), reqd: 1 },
		{ fieldname: "year", label: "Year", fieldtype: "Int", default: new Date().getFullYear(), reqd: 1 },
		{ fieldname: "job", label: "Job", fieldtype: "Link", options: "Job" },
		{ fieldname: "employee", label: "Worker", fieldtype: "Link", options: "Employee" },
		{ fieldname: "workstation", label: "Machine / Table", fieldtype: "Link", options: "Production Workstation" },
		{ fieldname: "status", label: "Status", fieldtype: "Select", options: "\nActive\nHold\nCompleted\nGate-Out Closed" },
	],
};
