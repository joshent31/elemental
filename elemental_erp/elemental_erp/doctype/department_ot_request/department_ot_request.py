import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


HR_REVIEW_ROLES = ("Elemental HR Gate HOD",)


class DepartmentOTRequest(Document):
	def validate(self):
		self.requested_by = self.requested_by or frappe.session.user
		self.request_key = f"{self.department}|{getdate(self.ot_date)}"
		if not self.employees:
			frappe.throw("Add at least one worker to the OT request.")
		seen = set()
		total = 0
		for row in self.employees:
			if row.employee in seen:
				frappe.throw(f"Employee {row.employee} is listed more than once.")
			seen.add(row.employee)
			employee = frappe.db.get_value(
				"Employee", row.employee, ["employee_name", "department", "status"], as_dict=True
			)
			if not employee or employee.status != "Active":
				frappe.throw(f"Employee {row.employee} is not active.")
			if employee.department != self.department:
				frappe.throw(
					f"{employee.employee_name} belongs to {employee.department or 'no department'}, "
					f"not {self.department}."
				)
			hours = float(row.requested_ot_hours or 0)
			if hours <= 0 or hours > 12:
				frappe.throw(f"Requested OT for {employee.employee_name} must be between 0 and 12 hours.")
			total += hours
		self.total_employees = len(seen)
		self.total_requested_ot_hours = round(total, 2)
		if self.docstatus == 0:
			self.status = "Draft"

	def on_submit(self):
		self.db_set("status", "Sent to HR", update_modified=False)
		self._assign_to_hr()

	def on_cancel(self):
		self.db_set({"status": "Cancelled", "request_key": None}, update_modified=False)

	def _assign_to_hr(self):
		from frappe.desk.form.assign_to import add

		users = frappe.get_all(
			"Has Role",
			filters={"role": "Elemental HR Gate HOD", "parenttype": "User"},
			pluck="parent",
			limit_page_length=0,
		)
		for user in users:
			if not frappe.db.get_value("User", user, "enabled"):
				continue
			try:
				add(
					{
						"assign_to": [user],
						"doctype": self.doctype,
						"name": self.name,
						"description": f"Review daily OT request for {self.department} on {self.ot_date}.",
					}
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"Could not assign OT Request {self.name} to {user}")


def _require_hr():
	roles = set(frappe.get_roles())
	if "System Manager" not in roles and not roles.intersection(HR_REVIEW_ROLES):
		frappe.throw("Only HR Gate HOD can review Department OT Requests.", frappe.PermissionError)


@frappe.whitelist()
def approve_ot_request(name, remarks=None):
	_require_hr()
	doc = frappe.get_doc("Department OT Request", name)
	if doc.docstatus != 1 or doc.status != "Sent to HR":
		frappe.throw("Only a submitted request waiting for HR can be approved.")
	frappe.db.set_value(
		doc.doctype,
		doc.name,
		{"status": "Approved", "reviewed_by": frappe.session.user, "reviewed_on": now_datetime(), "hr_remarks": remarks},
	)
	frappe.db.commit()
	return {"name": doc.name, "status": "Approved"}


@frappe.whitelist()
def reject_ot_request(name, remarks):
	_require_hr()
	if not (remarks or "").strip():
		frappe.throw("HR rejection remarks are required.")
	doc = frappe.get_doc("Department OT Request", name)
	if doc.docstatus != 1 or doc.status != "Sent to HR":
		frappe.throw("Only a submitted request waiting for HR can be rejected.")
	frappe.db.set_value(
		doc.doctype,
		doc.name,
		{"status": "Rejected", "reviewed_by": frappe.session.user, "reviewed_on": now_datetime(), "hr_remarks": remarks},
	)
	frappe.db.commit()
	return {"name": doc.name, "status": "Rejected"}
