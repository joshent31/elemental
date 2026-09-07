frappe.query_reports["Virtual FG Stock"] = {filters:[
	{fieldname:"customer",label:__("Customer"),fieldtype:"Link",options:"Customer"},
	{fieldname:"finished_good",label:__("Finished Good"),fieldtype:"Link",options:"Finished Good"},
	{fieldname:"source_job",label:__("Source Job"),fieldtype:"Link",options:"Job"},
	{fieldname:"intended_location",label:__("Location"),fieldtype:"Data"},
	{fieldname:"status",label:__("Status"),fieldtype:"Select",options:"\nAvailable\nPartly Reserved\nReserved\nPartly Utilized\nUtilized"}
]};
