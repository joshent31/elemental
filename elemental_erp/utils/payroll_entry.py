import frappe
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry

from elemental_erp.utils.salary_package import prepare_package_payroll_assignments


class ElementalPayrollEntry(PayrollEntry):
	@frappe.whitelist()
	def fill_employee_details(self):
		self.check_permission("write")
		self.validate_payroll_payable_account()
		prepare_package_payroll_assignments(self)
		return super().fill_employee_details()
