import frappe


def get_context(context):
	qr_value = frappe.form_dict.get("qr_value") or frappe.local.request.path.split("/")[-1]
	qr = frappe.db.get_value(
		"QR Code Master",
		{"qr_value": qr_value},
		["name", "job", "finished_good", "subpart_code", "subpart_name", "process", "total_qty", "completed_qty", "status"],
		as_dict=True,
	)
	context.no_cache = 1
	context.qr = qr
	context.qr_value = qr_value
	return context
