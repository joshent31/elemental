import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestSaturdayOff(unittest.TestCase):
	def test_leave_type_is_not_prorated_as_earned_leave(self):
		fixture = json.loads((ROOT / "fixtures" / "leave_type.json").read_text(encoding="utf-8"))[0]
		self.assertEqual(fixture["max_leaves_allowed"], 1)
		self.assertEqual(fixture["is_earned_leave"], 0)
		self.assertEqual(fixture["is_carry_forward"], 0)

	def test_scheduler_creates_exactly_one_calendar_month_allocation(self):
		source = (ROOT / "utils" / "saturday_off.py").read_text(encoding="utf-8")
		self.assertIn('"new_leaves_allocated": 1', source)
		self.assertIn('date.replace(day=1)', source)
		self.assertIn('calendar.monthrange', source)
		self.assertIn("COALESCE(employee_category, '') = 'Staff'", source)

	def test_daily_hook_and_single_day_validation_are_registered(self):
		hooks = (ROOT / "hooks.py").read_text(encoding="utf-8")
		validation = (ROOT / "utils" / "leave_validation.py").read_text(encoding="utf-8")
		self.assertIn('elemental_erp.utils.saturday_off.ensure_monthly_saturday_off_allocations', hooks)
		self.assertIn('must be a single-day leave application', validation)
		self.assertIn('available only for Staff employees', validation)

	def test_leave_policy_overlap_is_removed_and_blocked(self):
		source = (ROOT / "utils" / "saturday_off.py").read_text(encoding="utf-8")
		hooks = (ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn("remove_saturday_off_from_leave_policies", source)
		self.assertIn('frappe.db.delete("Leave Policy Detail"', source)
		self.assertIn("validate_leave_policy", source)
		self.assertIn("remove_saturday_off_from_leave_policies", hooks)
		self.assertIn('"Leave Policy"', hooks)
