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


def normalize_material_indent_departments():
	"""Convert unambiguous legacy indent department labels to Link values."""
	import frappe

	from elemental_erp.utils.transactions import resolve_department

	for indent in frappe.get_all(
		"Material Indent",
		filters={"department": ["!=", ""]},
		fields=["name", "department"],
	):
		canonical = resolve_department(indent.department)
		if canonical != indent.department and frappe.db.exists("Department", canonical):
			frappe.db.set_value(
				"Material Indent",
				indent.name,
				"department",
				canonical,
				update_modified=False,
			)


def backfill_material_indent_excess_stock():
	"""Populate the new display field on Material Indents saved before MOQ support."""
	import frappe

	if not frappe.db.has_column("Material Indent Item", "excess_stock_qty"):
		return
	frappe.db.sql(
		"""
		UPDATE `tabMaterial Indent Item`
		SET excess_stock_qty = GREATEST(
			COALESCE(available_qty, 0) - COALESCE(required_qty, 0),
			0
		)
		"""
	)


def sync_job_subpart_labels():
	"""Create the one-label-per-subpart traveller records for existing Jobs."""
	from elemental_erp.elemental_erp.doctype.job_subpart_label.job_subpart_label import (
		sync_job_subpart_labels as sync_labels,
	)

	sync_labels(refresh_existing=False)


def backfill_job_qr_codes():
	"""Give Jobs created before the Job-first scan workflow their permanent QR."""
	import frappe

	if not frappe.db.has_column("Job", "job_qr_value"):
		return
	from elemental_erp.elemental_erp.doctype.job.job import ensure_job_qr

	for job_name in frappe.get_all(
		"Job",
		filters={"job_qr_value": ["is", "not set"]},
		pluck="name",
		limit_page_length=0,
	):
		ensure_job_qr(job_name)
