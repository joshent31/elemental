"""Standalone tests for legacy-to-canonical Department resolution."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


TRANSACTIONS_PATH = Path(__file__).resolve().parents[2] / "utils" / "transactions.py"


def load_transactions(*, exact_exists, matches=()):
	frappe = types.ModuleType("frappe")
	frappe.db = types.SimpleNamespace(exists=Mock(return_value=exact_exists))
	frappe.get_all = Mock(return_value=list(matches))
	spec = importlib.util.spec_from_file_location("test_transactions_isolated", TRANSACTIONS_PATH)
	module = importlib.util.module_from_spec(spec)
	with patch.dict(sys.modules, {"frappe": frappe}):
		spec.loader.exec_module(module)
	return module, frappe


class TestDepartmentResolution(unittest.TestCase):
	def test_keeps_an_existing_department_link(self):
		transactions, frappe = load_transactions(exact_exists=True)
		self.assertEqual(transactions.resolve_department("Wood - EF"), "Wood - EF")
		frappe.get_all.assert_not_called()

	def test_resolves_a_unique_legacy_department_name(self):
		transactions, _ = load_transactions(exact_exists=False, matches=["Wood - EF"])
		self.assertEqual(transactions.resolve_department("Wood"), "Wood - EF")

	def test_does_not_guess_an_ambiguous_department(self):
		transactions, _ = load_transactions(
			exact_exists=False,
			matches=["Wood - EF", "Wood - ACME"],
		)
		self.assertEqual(transactions.resolve_department("Wood"), "Wood")


if __name__ == "__main__":
	unittest.main()
