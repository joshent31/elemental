"""Role gates shared by the authenticated mobile scan pages and APIs."""

from urllib.parse import quote

import frappe


DESIGN_SCAN_ROLES = ("Elemental Design User", "Elemental Design HOD")
QC_SCAN_ROLES = ("Elemental QC User", "Elemental QC HOD")
PRODUCTION_FLOOR_ROLES = ("Elemental Production User", "Elemental Production HOD")
PACKAGING_SCAN_ROLES = ("Elemental Packaging User", "Elemental Packaging HOD")
DISPATCH_SCAN_ROLES = ("Elemental Dispatch User", "Elemental Dispatch HOD")
GATE_SCAN_ROLES = ("Elemental HR Gate User", "Elemental HR Gate HOD")

PRODUCTION_SCAN_GROUPS = {
	"design": DESIGN_SCAN_ROLES,
	"qc": QC_SCAN_ROLES,
	"production": PRODUCTION_FLOOR_ROLES,
	"packaging": PACKAGING_SCAN_ROLES,
	"dispatch": DISPATCH_SCAN_ROLES,
}
PRODUCTION_SCAN_ROLES = tuple(
	dict.fromkeys(role for group in PRODUCTION_SCAN_GROUPS.values() for role in group)
)


def roles_allow(user_roles, allowed_roles):
	roles = set(user_roles or ())
	return "System Manager" in roles or bool(roles.intersection(allowed_roles))


def require_mobile_page(route, *allowed_roles):
	"""Redirect guests to login and reject signed-in users without a scan role."""
	if frappe.session.user == "Guest":
		request = getattr(frappe.local, "request", None)
		redirect_to = getattr(request, "full_path", None) or route
		redirect_to = redirect_to[:-1] if redirect_to.endswith("?") else redirect_to
		frappe.local.flags.redirect_location = f"/login?redirect-to={quote(redirect_to, safe='')}"
		raise frappe.Redirect

	roles = set(frappe.get_roles())
	if not roles_allow(roles, allowed_roles):
		frappe.throw(
			"Your user is not assigned a role for this mobile scan page.",
			frappe.PermissionError,
		)
	return roles


def production_menu_access(user_roles):
	return {
		name: roles_allow(user_roles, allowed_roles)
		for name, allowed_roles in PRODUCTION_SCAN_GROUPS.items()
	}
