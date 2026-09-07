frappe.query_reports["FG Change Audit"] = {
	filters: [
		{fieldname:"from_date",label:__("From Date"),fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-30),reqd:1},
		{fieldname:"to_date",label:__("To Date"),fieldtype:"Date",default:frappe.datetime.get_today(),reqd:1},
		{fieldname:"job",label:__("Job"),fieldtype:"Link",options:"Job"},
		{fieldname:"customer",label:__("Customer"),fieldtype:"Link",options:"Customer"},
		{fieldname:"finished_good",label:__("Finished Good"),fieldtype:"Link",options:"Finished Good"}
	]
};
