const elementalMonths = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	.map((label, index) => ({ label, value: String(index + 1) }));

frappe.query_reports["Job Completion"] = {
	filters: [
		{ fieldname: "month", label: __("Month"), fieldtype: "Select", options: elementalMonths },
		{ fieldname: "year", label: __("Year"), fieldtype: "Int", default: new Date().getFullYear() },
		{ fieldname: "job", label: __("Job"), fieldtype: "Link", options: "Job" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "status", label: __("Job Status"), fieldtype: "Select", options: "\nDraft\nJob Created\nIndent Raised\nIn Purchase\nIn Production\nIn Packaging\nMaterial Consumption Pending\nMaterial Consumed\nDispatched\nInstalled\nClosed\nCancelled" },
	],
};
