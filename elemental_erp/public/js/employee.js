frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new() || !(frappe.user.has_role("HR Manager") || frappe.user.has_role("System Manager"))) return;

		frm.add_custom_button(__("New Salary Package"), () => {
			frappe.new_doc("Employee Salary Package", {
				employee: frm.doc.name,
				effective_from: frappe.datetime.get_today(),
			});
		}, __("Payroll"));

		frm.add_custom_button(__("View Salary Packages"), () => {
			frappe.set_route("List", "Employee Salary Package", { employee: frm.doc.name });
		}, __("Payroll"));
	},
});
