// Client script for Salary Slip form.
// Auto-populates OT hours and amount for Worker-category employees.

frappe.ui.form.on("Salary Slip", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Show OT info for Workers
		if (frm.doc.employee) {
			frappe.db.get_value(
				"Employee",
				frm.doc.employee,
				["employee_category", "ctc", "standard_shift_hours"],
				(r) => {
					if (r && r.employee_category === "Worker") {
						frm.set_intro(
							`Worker — OT rate: Salary / Days / 8 = ${frm.doc.hourly_rate || "—"}/hr | ` +
							`OT capped at 15 hrs/month (govt norm)`,
							"blue"
						);

						// Add button to calculate OT
						frm.add_custom_button(
							"Calculate Worker OT",
							() => {
								frappe.confirm(
									"Calculate OT hours and amount for this Worker? " +
									"This will pull data from Employee Checkin for the slip period.",
									() => {
										frappe.call({
											method: "elemental_erp.api.calculate_slip_ot",
											args: {
												employee: frm.doc.employee,
												start_date: frm.doc.start_date,
												end_date: frm.doc.end_date,
											},
											callback: (r) => {
												if (r.message) {
													const ot = r.message;
													frm.set_value("overtime_hours", ot.ot_hours);
													frm.set_value("overtime_rate", ot.hourly_rate);
													frm.set_value("overtime_amount", ot.ot_amount);
													frm.refresh_fields([
														"overtime_hours",
														"overtime_rate",
														"overtime_amount",
													]);
													frappe.show_alert(
														`OT: ${ot.ot_hours_fmt} hrs × ${ot.hourly_rate} × 2 = ${ot.ot_amount_fmt}`
													);
												}
											},
										});
									}
								);
							},
							"Actions"
						).addClass("btn-primary");
					}
				}
			);
		}
	},
});
