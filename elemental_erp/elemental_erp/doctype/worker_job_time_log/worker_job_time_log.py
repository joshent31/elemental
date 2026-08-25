import frappe
from frappe.model.document import Document


class WorkerJobTimeLog(Document):
	def validate(self):
		if self.status == "Active":
			self.active_employee_key = self.employee
		else:
			self.active_employee_key = None
		if not self.is_new():
			stored = frappe.db.get_value(
				self.doctype,
				self.name,
				["employee", "job", "workstation", "work_date", "start_time", "hourly_rate"],
				as_dict=True,
			)
			for fieldname in ("employee", "job", "workstation", "work_date", "start_time", "hourly_rate"):
				if stored and stored.get(fieldname) != self.get(fieldname):
					frappe.throw(f"{self.meta.get_label(fieldname)} cannot be changed after the time log starts.")
		if self.end_time and self.start_time and self.end_time < self.start_time:
			frappe.throw("End time cannot be before start time.")
		if self.status == "Active" and self.end_time:
			frappe.throw("An Active worker allocation cannot have an end time.")
		if self.status != "Active" and not self.end_time:
			frappe.throw("A closed worker allocation requires an end time.")
