import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class TestFGChangeAndVirtualStock(unittest.TestCase):
	def load(self, relative):
		return json.loads((ROOT / relative).read_text(encoding="utf-8"))

	def test_fg_change_log_is_read_only_to_business_roles(self):
		doc = self.load("elemental_erp/doctype/job_fg_change_log/job_fg_change_log.json")
		for permission in doc["permissions"]:
			self.assertFalse(permission.get("create", 0))
			self.assertFalse(permission.get("write", 0))
			self.assertFalse(permission.get("delete", 0))

	def test_virtual_documents_are_submittable_and_named(self):
		for name in ("virtual_fg_transfer", "virtual_fg_reservation"):
			doc = self.load(f"elemental_erp/doctype/{name}/{name}.json")
			self.assertEqual(doc["is_submittable"], 1)
			self.assertEqual(doc["autoname"], "naming_series:")
			series = next(field for field in doc["fields"] if field["fieldname"] == "naming_series")
			self.assertTrue(series["default"].startswith("VF"))

	def test_stock_entry_and_customer_isolation_are_enforced(self):
		utility = (ROOT / "utils/fg_change_management.py").read_text(encoding="utf-8")
		reservation = (ROOT / "elemental_erp/doctype/virtual_fg_reservation/virtual_fg_reservation.py").read_text(encoding="utf-8")
		transfer = (ROOT / "elemental_erp/doctype/virtual_fg_transfer/virtual_fg_transfer.py").read_text(encoding="utf-8")
		self.assertIn('"doctype":"Stock Entry"', utility)
		self.assertIn('"doctype":"Stock Entry"', transfer)
		self.assertIn("customer-isolated", reservation)

	def test_scheduler_and_workspace_links_exist(self):
		hooks = (ROOT / "hooks.py").read_text(encoding="utf-8")
		workspace = self.load("elemental_erp/workspace/elemental_fixtures/elemental_fixtures.json")
		links = {row.get("link_to") for row in workspace["links"]}
		self.assertIn("send_daily_fg_change_digest", hooks)
		self.assertIn("FG Change Audit", links)
		self.assertIn("Virtual FG Stock", links)
		self.assertIn("Virtual FG Transfer", links)

	def test_no_ats_reference_in_new_workflow(self):
		for relative in ("utils/fg_change_management.py", "elemental_erp/doctype/virtual_fg_transfer/virtual_fg_transfer.py"):
			self.assertNotIn("ATS", (ROOT / relative).read_text(encoding="utf-8"))
