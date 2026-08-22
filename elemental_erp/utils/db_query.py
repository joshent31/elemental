"""Helpers for narrow Frappe database-query compatibility fixes."""


def strip_doctype_table_prefix(field, doctype):
	"""Remove only a DocType's exact main-table prefix from a field expression.

	Frappe already knows the main table for a ``DatabaseQuery``. Removing its
	prefix avoids keyword false positives for names such as ``Work from Home
	Request`` while leaving aliases, functions, and other SQL text intact for
	Frappe's own sanitizer to validate.
	"""
	if field is None:
		return None

	field = str(field)
	for prefix in (
		f"`tab{doctype}`.",
		f'"tab{doctype}".',
		f"tab{doctype}.",
	):
		field = field.replace(prefix, "")
	return field
