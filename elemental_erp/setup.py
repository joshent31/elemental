"""Installation and migration repairs for upstream ERPNext custom fields."""


def ensure_erpnext_address_and_contact_schema():
	"""Restore ERPNext's system-generated Address and Contact custom fields.

	ERPNext creates these fields in ``after_install``. A restored database can
	have the Custom Field document but not its table column; in that case the
	upstream helper sees no metadata change and does not run ``updatedb``. The
	explicit column check closes that recovery gap without altering healthy
	sites on every migration.
	"""
	import frappe
	from erpnext.setup.install import create_address_and_contact_custom_fields

	create_address_and_contact_custom_fields()
	if not frappe.db.has_column("Contact", "is_billing_contact"):
		frappe.clear_cache(doctype="Contact")
		frappe.db.updatedb("Contact")
