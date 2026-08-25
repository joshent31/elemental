frappe.query_reports["Worker Job Cost"] = {
	filters: [
		{ fieldname: "from_date", label: "From Date", fieldtype: "Date", default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: "To Date", fieldtype: "Date", default: frappe.datetime.month_end() },
		{ fieldname: "job", label: "Job", fieldtype: "Link", options: "Job" },
		{ fieldname: "employee", label: "Worker", fieldtype: "Link", options: "Employee" },
		{ fieldname: "workstation", label: "Machine / Table", fieldtype: "Link", options: "Production Workstation" },
		{ fieldname: "status", label: "Status", fieldtype: "Select", options: "\nActive\nHold\nCompleted\nGate-Out Closed" },
	],
};
