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
		controller = DOCTYPE_ROOT / "department_ot_request_employee" / "department_ot_request_employee.py"
		fields = {row.get("fieldname") for row in doc["fields"]}
		self.assertEqual(doc["istable"], 1)
		self.assertTrue({"employee", "requested_ot_hours", "reason"}.issubset(fields))
		self.assertTrue(controller.exists(), "Frappe requires the child DocType controller during migrate")
		self.assertIn("class DepartmentOTRequestEmployee(Document)", controller.read_text(encoding="utf-8"))

	def test_controller_enforces_department_and_hr_review(self):
		controller = (DOCTYPE_ROOT / "department_ot_request" / "department_ot_request.py").read_text(encoding="utf-8")
		self.assertIn("employee.department != self.department", controller)
		self.assertIn('employee.employee_category != "Worker"', controller)
		self.assertIn("OT can be requested only for Worker-category employees", controller)
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

	def test_payroll_uses_only_approved_ot_and_preserves_cash_adjustment(self):
		overtime = (APP_ROOT / "utils" / "worker_overtime.py").read_text(encoding="utf-8")
		self.assertIn('filters={"ot_date": date, "docstatus": 1, "status": "Approved"}', overtime)
		self.assertIn("min(float(actual_ot_hours or 0), requested)", overtime)
		self.assertIn("remaining_ot_hours = max(total_ot_hours - capped_ot_hours, 0)", overtime)
		self.assertIn("cash_adjustment = salary_slip_ot_amount / 2", overtime)
		self.assertIn("max(remaining_ot_value - cash_adjustment, 0)", overtime)
		self.assertIn("total_ot_payable = round(salary_slip_ot_amount + cash_to_worker, 2)", overtime)
		self.assertIn('"total_actual_ot_hours": total_actual_ot_hours', overtime)
		self.assertIn('"total_actual_ot_amount_1x": total_actual_ot_amount_1x', overtime)
		self.assertIn('calculate_ot = not has_cat or emp.employee_category == "Worker"', overtime)
		self.assertIn("approved_ot_hours(employee, date, actual_ot_hours) if calculate_ot else 0", overtime)
		self.assertIn('NORMAL_SHIFT_END = "18:00:00"', overtime)
		self.assertIn("def completed_ot_blocks(hours)", overtime)
		self.assertIn("math.floor((hours + 1e-9) / OT_BLOCK_HOURS) * OT_BLOCK_HOURS", overtime)
		self.assertIn("def calculate_actual_ot_hours(in_time, out_time, date, is_holiday=False)", overtime)
		self.assertIn('get_datetime(f"{date} {NORMAL_SHIFT_END}")', overtime)
		report = (APP_ROOT / "elemental_erp" / "report" / "worker_attendance_report" / "worker_attendance_report.py").read_text(encoding="utf-8")
		self.assertIn('"Cash Gross (1×)"', report)
		self.assertIn('"Less Slip OT ÷ 2"', report)
		self.assertIn('day_info.get("actual_ot_hours", 0)', report)
		self.assertIn('"Actual OT Hrs"', report)
		self.assertIn('"Actual OT Value (1×)"', report)
		self.assertIn('"Actual OT Hours", "values": actual_values', report)

	def test_government_report_separates_actual_from_approved_ot(self):
		report = (
			APP_ROOT / "elemental_erp" / "report" / "worker_ot_summary" / "worker_ot_summary.py"
		).read_text(encoding="utf-8")
		self.assertIn('day_info.get("actual_ot_hours", 0)', report)
		self.assertIn('"Actual OT Hrs"', report)
		self.assertIn('"Approved OT Hrs"', report)
		self.assertIn('"Actual OT"', report)
		self.assertIn('"Approved OT"', report)

	def test_reconciliation_uses_same_1800_half_hour_rule(self):
		report = (REPORT_ROOT / "ot_request_vs_checkout.py").read_text(encoding="utf-8")
		self.assertIn("from elemental_erp.utils.worker_overtime import calculate_actual_ot_hours", report)
		self.assertIn("actual_ot = calculate_actual_ot_hours(", report)


if __name__ == "__main__":
	unittest.main()
