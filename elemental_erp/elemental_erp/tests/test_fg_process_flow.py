"""Static regression checks for persistent Finished Good process selections."""

import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[2]
FG_SUBPART = APP_ROOT / "elemental_erp" / "doctype" / "fg_subpart" / "fg_subpart.json"
FINISHED_GOOD = APP_ROOT / "elemental_erp" / "doctype" / "finished_good" / "finished_good.py"
SETUP = APP_ROOT / "setup.py"
HOOKS = APP_ROOT / "hooks.py"
CLIENT = APP_ROOT / "public" / "js" / "finished_good.js"
TRAVELLER = APP_ROOT / "elemental_erp" / "print_format" / "job_production_traveller" / "job_production_traveller.json"


class TestFinishedGoodProcessFlow(unittest.TestCase):
	def test_legacy_migration_accepts_frappe_dict_without_callable_set(self):
		class FrappeDict(dict):
			def __getattr__(self, key):
				return self.get(key)

		frappe = types.ModuleType("frappe")
		model = types.ModuleType("frappe.model")
		document = types.ModuleType("frappe.model.document")
		document.Document = object
		modules = {
			"frappe": frappe,
			"frappe.model": model,
			"frappe.model.document": document,
		}
		controller_path = APP_ROOT / "elemental_erp" / "doctype" / "finished_good" / "finished_good.py"
		import importlib.util
		spec = importlib.util.spec_from_file_location("test_finished_good_processes", controller_path)
		module = importlib.util.module_from_spec(spec)
		with patch.dict(sys.modules, modules):
			spec.loader.exec_module(module)
		row = FrappeDict(processes="Metal\nPacking")
		self.assertEqual(module.selected_processes(row), ["Metal", "Packing"])
		self.assertEqual(row["process_metal"], 1)
		self.assertEqual(row["process_packing"], 1)
		self.assertEqual(row["process_wood"], 0)

	def test_processes_are_persistent_checkboxes_with_read_only_summary(self):
		doctype = json.loads(FG_SUBPART.read_text(encoding="utf-8"))
		fields = {field["fieldname"]: field for field in doctype["fields"] if field.get("fieldname")}
		for fieldname in (
			"process_metal", "process_wood", "process_electrical", "process_powdercoating",
			"process_paint", "process_us_assembly", "process_packing",
		):
			self.assertEqual(fields[fieldname]["fieldtype"], "Check")
		self.assertEqual(fields["process_flow"]["read_only"], 1)
		self.assertEqual(fields["process_flow"]["in_list_view"], 1)
		self.assertTrue(fields["processes"]["hidden"])

	def test_save_builds_ordered_flow_and_legacy_storage(self):
		source = FINISHED_GOOD.read_text(encoding="utf-8")
		self.assertIn('row.process_flow = " → ".join(processes)', source)
		self.assertIn('row.processes = "\\n".join(processes)', source)
		self.assertIn("selected_processes(row, migrate_legacy=False)", source)
		self.assertIn("Select at least one process", source)
		for label in ("Metal", "Wood", "Electrical", "Powdercoating", "Paint", "US Assembly", "Packing"):
			self.assertIn(f'"{label}"', source)

	def test_checkbox_changes_immediately_refresh_grid_summary(self):
		client = CLIENT.read_text(encoding="utf-8")
		hooks = HOOKS.read_text(encoding="utf-8")
		self.assertIn('"Finished Good": "public/js/finished_good.js"', hooks)
		self.assertIn('selected.join(" → ")', client)
		self.assertIn('selected.join("\\n")', client)
		self.assertIn('frappe.ui.form.on("FG Subpart"', client)

	def test_migration_backfills_existing_subparts_before_label_sync(self):
		setup = SETUP.read_text(encoding="utf-8")
		hooks = HOOKS.read_text(encoding="utf-8")
		self.assertIn("def backfill_fg_subpart_process_checks", setup)
		self.assertLess(
			hooks.index("backfill_fg_subpart_process_checks"),
			hooks.index("sync_job_subpart_labels"),
		)

	def test_traveller_prints_tracker_processes_selected_from_finished_good(self):
		html = json.loads(TRAVELLER.read_text(encoding="utf-8"))["html"]
		self.assertIn("Process Flow", html)
		self.assertIn("process.process_name", html)


if __name__ == "__main__":
	unittest.main()
