import frappe

from elemental_erp.utils.mobile_access import require_mobile_page


def get_context(context):
	require_mobile_page("/worker-job-scan", "Elemental Production HOD")
	context.no_cache = 1
	context.prefill_workstation = frappe.form_dict.get("workstation") or ""
	return context
