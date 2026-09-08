import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]


class TestDayEndAttendance(unittest.TestCase):
	def test_settings_are_optional_and_default_off(self):
		doc = json.loads((APP_ROOT / "elemental_erp/doctype/elemental_attendance_settings/elemental_attendance_settings.json").read_text(encoding="utf-8"))
		field = next(row for row in doc["fields"] if row["fieldname"] == "enable_elemental_day_end_attendance")
		self.assertEqual(field["default"], "0")

	def test_day_end_engine_handles_present_absent_and_protected_days(self):
		source = (APP_ROOT / "employee_gate.py").read_text(encoding="utf-8")
		self.assertIn('"status":"Present" if present else "Absent"', source)
		self.assertIn("_is_non_working_day", source)
		self.assertIn("_has_approved_leave", source)
		self.assertIn("_has_approved_wfh", source)
		self.assertIn("default_holiday_list", source)
		self.assertIn('"Attendance"', source)
		self.assertIn('"Employee Checkin"', source)

	def test_shift_auto_attendance_toggle_is_reversible(self):
		source = (APP_ROOT / "elemental_erp/doctype/elemental_attendance_settings/elemental_attendance_settings.py").read_text(encoding="utf-8")
		self.assertIn('"enable_auto_attendance", 0', source)
		self.assertIn('"enable_auto_attendance", 1', source)
		self.assertIn("disabled_shift_types_json", source)

	def test_hourly_scheduler_calls_day_end_guard(self):
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn('"hourly": ["elemental_erp.employee_gate.scheduled_day_end_attendance"]', hooks)

	def test_wfh_respects_employee_holiday_calendar(self):
		source = (APP_ROOT / "elemental_erp/doctype/work_from_home_request/work_from_home_request.py").read_text(encoding="utf-8")
		self.assertIn("_is_non_working_day", source)
		self.assertIn("skipped, holiday/week off", source)
