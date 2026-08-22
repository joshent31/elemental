"""Regression tests for migration-time schema repairs."""

import sys
import types
import unittest
from unittest.mock import Mock, patch

from elemental_erp.setup import ensure_erpnext_address_and_contact_schema


def fake_modules(has_column):
	frappe = types.ModuleType("frappe")
	frappe.db = types.SimpleNamespace(
		has_column=Mock(return_value=has_column),
		updatedb=Mock(),
	)
	frappe.clear_cache = Mock()

	erpnext = types.ModuleType("erpnext")
	erpnext.__path__ = []
	setup = types.ModuleType("erpnext.setup")
	setup.__path__ = []
	install = types.ModuleType("erpnext.setup.install")
	install.create_address_and_contact_custom_fields = Mock()
	return frappe, install, {
		"frappe": frappe,
		"erpnext": erpnext,
		"erpnext.setup": setup,
		"erpnext.setup.install": install,
	}


class TestERPNextContactSchemaRepair(unittest.TestCase):
	def test_rebuilds_contact_table_when_column_is_missing(self):
		frappe, install, modules = fake_modules(has_column=False)
		with patch.dict(sys.modules, modules):
			ensure_erpnext_address_and_contact_schema()

		install.create_address_and_contact_custom_fields.assert_called_once_with()
		frappe.clear_cache.assert_called_once_with(doctype="Contact")
		frappe.db.updatedb.assert_called_once_with("Contact")

	def test_healthy_schema_is_not_rebuilt(self):
		frappe, install, modules = fake_modules(has_column=True)
		with patch.dict(sys.modules, modules):
			ensure_erpnext_address_and_contact_schema()

		install.create_address_and_contact_custom_fields.assert_called_once_with()
		frappe.clear_cache.assert_not_called()
		frappe.db.updatedb.assert_not_called()


if __name__ == "__main__":
	unittest.main()
