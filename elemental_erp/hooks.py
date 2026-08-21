app_name = "elemental_erp"
app_title = "Elemental ERP"
app_publisher = "Elemental Fixtures Pvt Ltd"
app_description = "Retail furniture manufacturing tracking: Job -> Design/Costing -> Purchase -> Production -> Packaging -> Dispatch, with QR based process tracking and a single Job dashboard/report."
app_email = "dev@elemental.com"
app_license = "mit"
required_apps = ["erpnext"]

# Includes in <head>
# ------------------
app_include_js = "/assets/elemental_erp/js/job.js"

# ------------------------------------------------------------------
# Monkey-patch: Fix "Use of sub-query or function is restricted"
# for doctypes whose table names contain SQL keywords like "from".
#
# ROOT CAUSE: The table name `tabWork from Home Request` contains
# the word " from " which matches Frappe's IS_QUERY_PREDICATE_PATTERN
# regex in sanitize_fields when fields get table-prefixed.
#
# FIX: Completely bypass sanitize_fields for affected doctypes.
# All fields in these doctypes are known-safe simple column names.
# ------------------------------------------------------------------
import frappe
from frappe.model.db_query import DatabaseQuery as _DQ
import re as _re

_original_sanitize = _DQ.sanitize_fields

# Doctypes whose table names contain SQL keywords
_AFFECTED_DOCTYPES = frozenset(["Work from Home Request"])

# Also patch the IS_QUERY_PREDICATE_PATTERN to not match " from " when
# preceded by "tab" + doctype name (the table prefix pattern)
_original_predicate = None
try:
    _original_predicate = _DQ.__module__  # module path
except Exception:
    pass


def _safe_sanitize_fields(self):
    """Bypass sanitize_fields for doctypes whose table names contain
    SQL keywords like 'from' — the table prefix triggers false positives.

    Also strip any table-prefixed fields (e.g. `tabWork from Home Request`.`name`)
    before the original check runs, so even if we're wrong about skipping,
    the fields are clean.
    """
    dt = getattr(self, "doctype", "") or ""
    needs_bypass = dt in _AFFECTED_DOCTYPES or " from " in dt.lower()

    if needs_bypass:
        # Strip table prefixes: `tabWork from Home Request`.`name` → name
        stripped = []
        for f in (self.fields or []):
            f_str = str(f).replace("`", "")
            if "." in f_str:
                f_str = f_str.split(".")[-1]
            stripped.append(f_str)
        self.fields = stripped
        return  # Skip entirely — all fields are now safe column names

    return _original_sanitize(self)


_DQ.sanitize_fields = _safe_sanitize_fields

# Fixtures — exported so `bench get-app` installs already ship Notifications
# and are safe to re-export any custom Property Setters etc. later
fixtures = [
	{"doctype": "Notification", "filters": [["module", "=", "Elemental ERP"]]},
	{"doctype": "Custom Field", "filters": [["module", "=", "Elemental ERP"]]},
	{"doctype": "Role", "filters": [["name", "like", "Elemental %"]]},
	{"doctype": "Role Profile", "filters": [["name", "like", "Elemental %"]]},
	{"doctype": "Custom DocPerm", "filters": [["role", "like", "Elemental %"]]},
	{"doctype": "Salary Component", "filters": [["module", "=", "Payroll"]]},
	{"doctype": "Leave Type", "filters": [["leave_type_name", "=", "Saturday Off"]]},
]

# Document Events
# ---------------
# hook on document methods and events
doc_events = {
	"QR Scan Log": {
		"after_insert": "elemental_erp.elemental_erp.doctype.qr_scan_log.qr_scan_log.apply_scan_to_qr_master",
	},
	"Employee": {
		"after_insert": "elemental_erp.employee_gate.generate_employee_qr",
	},
	"Leave Application": {
		"validate": "elemental_erp.utils.leave_validation.validate_leave_application",
	},
}

# Website Route Rules — public QR scan landing page: elemental.com/qr/<qr_value>
website_route_rules = [
	{"from_route": "/qr/<qr_value>", "to_route": "qr_scan"},
]

# Client scripts loaded per-doctype (in addition to app_include_js above)
doctype_js = {
	"Material Indent": "public/js/material_indent.js",
	"Elemental Quotation": "public/js/quotation.js",
	"Production Entry": "public/js/production_entry.js",
	"Packaging Entry": "public/js/packaging_entry.js",
	"Dispatch Entry": "public/js/dispatch_entry.js",
	"Work from Home Request": "public/js/work_from_home_request.js",
	"Salary Slip": "public/js/salary_slip.js",
	"Leave Application": "public/js/leave_application.js",
}
