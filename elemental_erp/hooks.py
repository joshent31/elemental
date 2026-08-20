app_name = "elemental_erp"
app_title = "Elemental ERP"
app_publisher = "Elemental Fixtures Pvt Ltd"
app_description = "Retail furniture manufacturing tracking: Job -> Design/Costing -> Purchase -> Production -> Packaging -> Dispatch, with QR based process tracking and a single Job dashboard/report."
app_email = "dev@elemental.com"
app_license = "mit"
required_apps = ["erpnext"]

# Includes in <head>
# ------------------
app_include_js = "/assets/elemental_erp/js/job.js"

# Fixtures — exported so `bench get-app` installs already ship Notifications
# and are safe to re-export any custom Property Setters etc. later
fixtures = [
	{"doctype": "Notification", "filters": [["module", "=", "Elemental ERP"]]},
	{"doctype": "Custom Field", "filters": [["module", "=", "Elemental ERP"]]},
	{"doctype": "Role", "filters": [["name", "like", "Elemental %"]]},
	{"doctype": "Role Profile", "filters": [["name", "like", "Elemental %"]]},
	{"doctype": "Custom DocPerm", "filters": [["role", "like", "Elemental %"]]},
]

# Document Events
# ---------------
# hook on document methods and events

doc_events = {
	"QR Scan Log": {
		"after_insert": "elemental_erp.elemental_erp.doctype.qr_scan_log.qr_scan_log.apply_scan_to_qr_master",
	},
	"Employee": {
		"after_insert": "elemental_erp.employee_gate.generate_employee_qr",
	},
}

# Website Route Rules — public QR scan landing page: elemental.com/qr/<qr_value>
website_route_rules = [
	{"from_route": "/qr/<qr_value>", "to_route": "qr_scan"},
]

# Client scripts loaded per-doctype (in addition to app_include_js above)
doctype_js = {
	"Material Indent": "public/js/material_indent.js",
	"Elemental Quotation": "public/js/quotation.js",
	"Production Entry": "public/js/production_entry.js",
	"Packaging Entry": "public/js/packaging_entry.js",
	"Dispatch Entry": "public/js/dispatch_entry.js",
}
