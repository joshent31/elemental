import frappe

from elemental_erp.utils.mobile_access import DISPATCH_SCAN_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/dispatch-scan", *DISPATCH_SCAN_ROLES)
	context.no_cache = 1
	return context
