import frappe
from frappe.model.document import Document


class JobDepartmentStatus(Document):
	pass


def get_or_create(job, department):
	name = f"{job}-{department}"
	if frappe.db.exists("Job Department Status", name):
		return frappe.get_doc("Job Department Status", name)
	doc = frappe.get_doc(
		{
			"doctype": "Job Department Status",
			"job": job,
			"department": department,
			"status": "Open",
			"total_qty_received": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc
