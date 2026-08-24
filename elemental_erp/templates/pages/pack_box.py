import frappe

from elemental_erp.utils.mobile_access import (
	PACKAGING_SCAN_ROLES,
	PRODUCTION_SCAN_ROLES,
	require_mobile_page,
	roles_allow,
)


def get_context(context):
	roles = require_mobile_page("/pack-box", *PRODUCTION_SCAN_ROLES)
	context.no_cache = 1
	context.prefill_box = frappe.form_dict.get("box") or ""
	context.prefill_job = frappe.form_dict.get("job") or ""
	context.can_pack = roles_allow(roles, PACKAGING_SCAN_ROLES)
	return context
