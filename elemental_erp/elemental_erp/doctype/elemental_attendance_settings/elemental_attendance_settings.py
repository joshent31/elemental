import json

import frappe
from frappe.model.document import Document


class ElementalAttendanceSettings(Document):
	def validate(self):
		if not 0 <= int(self.day_end_hour or 23) <= 23:
			frappe.throw("Day End Processing Hour must be between 0 and 23.")

	def on_update(self):
		"""Make custom and HRMS auto-attendance mutually exclusive and reversible."""
		if self.enable_elemental_day_end_attendance:
			enabled = frappe.get_all("Shift Type", {"enable_auto_attendance": 1}, pluck="name")
			if enabled:
				remembered = set(json.loads(self.disabled_shift_types_json or "[]"))
				remembered.update(enabled)
				for shift_type in enabled:
					frappe.db.set_value("Shift Type", shift_type, "enable_auto_attendance", 0, update_modified=False)
				self.db_set("disabled_shift_types_json", json.dumps(sorted(remembered)), update_modified=False)
		else:
			for shift_type in json.loads(self.disabled_shift_types_json or "[]"):
				if frappe.db.exists("Shift Type", shift_type):
					frappe.db.set_value("Shift Type", shift_type, "enable_auto_attendance", 1, update_modified=False)
			self.db_set("disabled_shift_types_json", "[]", update_modified=False)
