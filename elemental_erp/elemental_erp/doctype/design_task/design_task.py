import frappe
from frappe.model.document import Document

from elemental_erp.utils.costing import compute_cost
from elemental_erp.utils.transactions import assert_active_job


class DesignTask(Document):
	def validate(self):
		assert_active_job(self.job)

	def compute_time_and_cost(self):
		if self.start_time and self.end_time:
			seconds = frappe.utils.time_diff_in_seconds(self.end_time, self.start_time)
			self.hours_spent = round(seconds / 3600, 2)
			self.design_cost = compute_cost(self.assigned_designer, self.hours_spent)
