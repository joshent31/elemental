import frappe

from elemental_erp.utils.mobile_access import PACKAGING_SCAN_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/pack-box", *PACKAGING_SCAN_ROLES)
	context.no_cache = 1
	context.prefill_box = frappe.form_dict.get("box") or ""
	return context
