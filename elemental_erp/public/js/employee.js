frappe.ui.form.on("Employee", {
	onload(frm) {
		// Frappe's Duplicate action copies read-only custom fields. Clear the
		// source employee's gate identity immediately on the unsaved form; the
		// server generates a new QR after this Employee is inserted.
		if (frm.is_new() && (frm.doc.employee_qr_value || frm.doc.employee_qr_image)) {
			frm.set_value("employee_qr_value", "");
			frm.set_value("employee_qr_image", "");
		}
	},

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
