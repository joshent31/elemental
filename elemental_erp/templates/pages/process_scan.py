import frappe

from elemental_erp.utils.mobile_access import PRODUCTION_FLOOR_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/process-scan", *PRODUCTION_FLOOR_ROLES)
	context.no_cache = 1
	context.prefill_part = frappe.form_dict.get("part") or ""
	return context
