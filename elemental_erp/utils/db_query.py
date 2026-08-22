"""Helpers for narrow Frappe database-query compatibility fixes."""

_AFFECTED_DOCTYPES = frozenset(["Work from Home Request"])


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


def normalize_database_query_fields(query):
	"""Normalize affected main-table prefixes on a DatabaseQuery instance."""
	doctype = getattr(query, "doctype", "") or ""
	if doctype not in _AFFECTED_DOCTYPES:
		return False

	query.fields = [strip_doctype_table_prefix(field, doctype) for field in (query.fields or [])]
	return True


def install_database_query_compatibility():
	"""Install the idempotent sanitizer wrapper before Frappe handles a request.

	Only the exact affected main-table prefix is removed. Frappe's original
	sanitizer still validates every normalized expression.
	"""
	from frappe.model.db_query import DatabaseQuery

	current = DatabaseQuery.sanitize_fields
	if getattr(current, "_elemental_wfh_compatibility", False):
		return

	original = getattr(current, "_elemental_original_sanitize_fields", current)

	def sanitize_fields(query):
		normalize_database_query_fields(query)
		return original(query)

	sanitize_fields._elemental_wfh_compatibility = True
	sanitize_fields._elemental_original_sanitize_fields = original
	DatabaseQuery.sanitize_fields = sanitize_fields
