"""Audit all standalone Elemental DocType naming rules."""

import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = APP_ROOT / "elemental_erp" / "doctype"

EXPECTED_SERIES = {
	"Annual Salary Revision": "ASR-.YYYY.-.#####",
	"Department OT Request": "OTR-.YYYY.-",
	"Department Transfer": "TRF-.YYYY.-",
	"Dispatch Entry": "DSP-.YYYY.-",
	"Elemental Quotation": "QTN-.YYYY.-",
	"Employee Salary Package": "ESP-.YYYY.-.#####",
	"Job": "JOB-.YYYY.-",
	"Job Subpart Label": "JSL-.YYYY.-",
	"Material Indent": "IND-.YYYY.-",
	"Material Issue": "MISS-.YYYY.-",
	"Packaging Entry": "PKG-.YYYY.-",
	"Packing Box": "PBOX-.YYYY.-",
	"Production Entry": "PRD-.YYYY.-",
	"QR Code Master": "QRM-.YYYY.-",
	"QR Scan Log": "QSL-.YYYY.-",
	"Work from Home Request": "WFH-.YYYY.-",
	"Worker Job Time Log": "WJTL-.YYYY.-",
}


class TestNamingSeriesAudit(unittest.TestCase):
	def load_doctypes(self):
		return {
			doc["name"]: doc
			for path in DOCTYPE_ROOT.glob("*/*.json")
			if (doc := json.loads(path.read_text(encoding="utf-8"))).get("doctype") == "DocType"
			and not doc.get("istable")
		}

	def test_transaction_doctypes_use_related_series(self):
		doctypes = self.load_doctypes()
		for name, series in EXPECTED_SERIES.items():
			with self.subTest(doctype=name):
				doc = doctypes[name]
				self.assertEqual(doc.get("autoname"), "naming_series:")
				field = next(row for row in doc["fields"] if row.get("fieldname") == "naming_series")
				self.assertEqual(field.get("options"), series)
				self.assertEqual(field.get("default"), series)

	def test_master_codes_are_auto_generated_and_read_only(self):
		doctypes = self.load_doctypes()
		fg = doctypes["Finished Good"]
		fg_fields = {row["fieldname"]: row for row in fg["fields"] if row.get("fieldname")}
		self.assertEqual(fg["autoname"], "field:fg_code")
		self.assertEqual(fg_fields["naming_series"]["options"], "FG-.#####")
		self.assertEqual(fg_fields["fg_code"]["read_only"], 1)
		fg_controller = (DOCTYPE_ROOT / "finished_good" / "finished_good.py").read_text(encoding="utf-8")
		self.assertIn('self.fg_code = make_autoname(self.naming_series or "FG-.#####")', fg_controller)

		workstation = doctypes["Production Workstation"]
		ws_fields = {row["fieldname"]: row for row in workstation["fields"] if row.get("fieldname")}
		self.assertEqual(workstation["autoname"], "field:workstation_code")
		self.assertEqual(ws_fields["naming_series"]["options"], "WS-.#####")
		self.assertEqual(ws_fields["workstation_code"]["read_only"], 1)

	def test_all_standalone_doctypes_have_an_explicit_naming_strategy(self):
		for name, doc in self.load_doctypes().items():
			with self.subTest(doctype=name):
				self.assertTrue(doc.get("autoname"), f"{name} has no autoname strategy")


if __name__ == "__main__":
	unittest.main()
