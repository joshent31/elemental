"""Keep the Elemental Fixtures workspace aligned with standalone DocTypes."""

import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = APP_ROOT / "elemental_erp" / "doctype"
WORKSPACE_PATH = (
	APP_ROOT
	/ "elemental_erp"
	/ "workspace"
	/ "elemental_fixtures"
	/ "elemental_fixtures.json"
)


class TestElementalFixturesWorkspace(unittest.TestCase):
	def test_contains_every_standalone_elemental_doctype_and_no_child_tables(self):
		standalone = set()
		child_tables = set()
		for path in DOCTYPE_ROOT.glob("*/*.json"):
			doctype = json.loads(path.read_text(encoding="utf-8"))
			if doctype.get("doctype") != "DocType" or doctype.get("module") != "Elemental ERP":
				continue
			target = child_tables if doctype.get("istable") else standalone
			target.add(doctype["name"])

		workspace = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
		links = [
			link["link_to"]
			for link in workspace["links"]
			if link.get("link_type") == "DocType"
		]

		self.assertEqual(set(links), standalone)
		self.assertEqual(len(links), len(set(links)), "Workspace contains duplicate DocType links")
		self.assertTrue(set(links).isdisjoint(child_tables))


if __name__ == "__main__":
	unittest.main()
