"""Regression checks for Material Indent to Material Issue linkage."""

import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]


class TestMaterialIssueLinkage(unittest.TestCase):
	def test_indent_department_is_a_department_link(self):
		doctype = json.loads(
			(APP_ROOT / "elemental_erp" / "doctype" / "material_indent" / "material_indent.json").read_text(
				encoding="utf-8"
			)
		)
		department = next(field for field in doctype["fields"] if field.get("fieldname") == "department")
		self.assertEqual(department["fieldtype"], "Link")
		self.assertEqual(department["options"], "Department")

	def test_material_issue_client_script_is_registered(self):
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn('"Material Issue": "public/js/material_issue.js"', hooks)


if __name__ == "__main__":
	unittest.main()
