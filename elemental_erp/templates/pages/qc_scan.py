import frappe

from elemental_erp.utils.mobile_access import QC_SCAN_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/qc-scan", *QC_SCAN_ROLES)
	context.no_cache = 1
	context.prefill_qr = frappe.form_dict.get("qr") or ""
	context.employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name"],
		limit_page_length=0,
	)
	return context
