import frappe


def get_context(context):
	context.no_cache = 1
	context.prefill_qr = frappe.form_dict.get("qr") or ""
	departments = frappe.get_all("Department", fields=["name"], limit_page_length=0)
	context.departments = departments
	return context
