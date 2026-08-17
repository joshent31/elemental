import frappe


def get_context(context):
	context.no_cache = 1
	context.prefill_qr = frappe.form_dict.get("qr") or ""
	context.employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name"],
		limit_page_length=0,
	)
	return context
