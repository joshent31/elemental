frappe.ui.form.on("Elemental Attendance Settings", {
	refresh(frm) {
		frm.add_custom_button("Run for Today", () => {
			frappe.confirm("Process attendance for all active employees for today? Existing Attendance, Sundays, holidays and approved leave will be skipped.", () => {
				frappe.call({
					method:"elemental_erp.employee_gate.run_day_end_attendance",
					args:{attendance_date:frappe.datetime.get_today(), force:1},
					freeze:true,
					freeze_message:__("Processing day-end attendance..."),
					callback:(r) => { frappe.msgprint(r.message.message || r.message.summary); frm.reload_doc(); }
				});
			});
		}).addClass("btn-primary");
	}
});
