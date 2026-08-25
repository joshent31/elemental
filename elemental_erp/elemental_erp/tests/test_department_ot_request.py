"""Static regression tests for daily department OT authorization."""

import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = APP_ROOT / "elemental_erp" / "doctype"
REPORT_ROOT = APP_ROOT / "elemental_erp" / "report" / "ot_request_vs_checkout"


class TestDepartmentOTRequest(unittest.TestCase):
	def test_request_is_submittable_and_has_employee_table(self):
		doc = json.loads((DOCTYPE_ROOT / "department_ot_request" / "department_ot_request.json").read_text(encoding="utf-8"))
		fields = {row.get("fieldname"): row for row in doc["fields"]}
		self.assertEqual(doc["autoname"], "naming_series:")
		self.assertEqual(doc["is_submittable"], 1)
		self.assertEqual(fields["employees"]["options"], "Department OT Request Employee")
		self.assertEqual(fields["request_key"]["unique"], 1)

	def test_child_captures_worker_hours_and_reason(self):
		doc = json.loads((DOCTYPE_ROOT / "department_ot_request_employee" / "department_ot_request_employee.json").read_text(encoding="utf-8"))
		fields = {row.get("fieldname") for row in doc["fields"]}
		self.assertEqual(doc["istable"], 1)
		self.assertTrue({"employee", "requested_ot_hours", "reason"}.issubset(fields))

	def test_controller_enforces_department_and_hr_review(self):
		controller = (DOCTYPE_ROOT / "department_ot_request" / "department_ot_request.py").read_text(encoding="utf-8")
		self.assertIn("employee.department != self.department", controller)
		self.assertIn("hours <= 0 or hours > 12", controller)
		self.assertIn('self.db_set("status", "Sent to HR"', controller)
		self.assertIn("def approve_ot_request", controller)
		self.assertIn("def reject_ot_request", controller)

	def test_reconciliation_report_has_payable_controls(self):
		report = (REPORT_ROOT / "ot_request_vs_checkout.py").read_text(encoding="utf-8")
		self.assertIn('"Employee Checkin"', report)
		self.assertIn('return "Unauthorized OT"', report)
		self.assertIn('return "Rejected OT Worked"', report)
		self.assertIn('request_status == "Approved"', report)
		self.assertIn("min(requested, actual)", report)


if __name__ == "__main__":
	unittest.main()
