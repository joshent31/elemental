import frappe

from elemental_erp.utils.mobile_access import PRODUCTION_FLOOR_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/transfer-in", *PRODUCTION_FLOOR_ROLES)
	context.no_cache = 1
	context.prefill_qr = frappe.form_dict.get("qr") or ""
	departments = frappe.get_all("Department", fields=["name"], limit_page_length=0)
	context.departments = departments
	return context
