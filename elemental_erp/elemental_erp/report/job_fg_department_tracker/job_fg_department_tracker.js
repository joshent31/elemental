const elementalMonths = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	.map((label, index) => ({ label, value: String(index + 1) }));

frappe.query_reports["Job FG Department Tracker"] = {
	filters: [
		{ fieldname: "month", label: __("Month"), fieldtype: "Select", options: elementalMonths },
		{ fieldname: "year", label: __("Year"), fieldtype: "Int", default: new Date().getFullYear() },
		{ fieldname: "job", label: __("Job"), fieldtype: "Link", options: "Job" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "finished_good", label: __("Finished Good"), fieldtype: "Link", options: "Finished Good" },
		{ fieldname: "process_name", label: __("Process"), fieldtype: "Select", options: "\nMetal\nWood\nElectrical\nPowdercoating\nPaint\nUS Assembly\nPacking" },
		{ fieldname: "department", label: __("Lying Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "tracker_status", label: __("Tracker Status"), fieldtype: "Select", options: "\nPending\nIn Process\nCompleted" },
	],
};
