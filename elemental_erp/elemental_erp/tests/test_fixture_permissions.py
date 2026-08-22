"""Regression tests for permissions shipped as fixtures."""

import json
import unittest
from pathlib import Path


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "custom_docperm.json"
ITEM_EDITOR_ROLES = {
	"Elemental Costing User",
	"Elemental Costing HOD",
	"Elemental Purchase User",
	"Elemental Purchase HOD",
}
ITEM_READ_ONLY_ROLES = {
	"Elemental Production User",
	"Elemental Production HOD",
}


class TestItemPermissions(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		permissions = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
		cls.item_permissions = {
			permission["role"]: permission
			for permission in permissions
			if permission.get("parent") == "Item"
		}

	def test_costing_and_purchase_can_create_and_edit_items(self):
		for role in ITEM_EDITOR_ROLES:
			with self.subTest(role=role):
				permission = self.item_permissions[role]
				self.assertEqual(permission["read"], 1)
				self.assertEqual(permission["create"], 1)
				self.assertEqual(permission["write"], 1)
				self.assertEqual(permission["delete"], 0)

	def test_production_item_access_remains_read_only(self):
		for role in ITEM_READ_ONLY_ROLES:
			with self.subTest(role=role):
				permission = self.item_permissions[role]
				self.assertEqual(permission["read"], 1)
				self.assertEqual(permission["create"], 0)
				self.assertEqual(permission["write"], 0)


if __name__ == "__main__":
	unittest.main()
