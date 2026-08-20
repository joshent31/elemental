// Client script for Work from Home Request form.
// Adds: approve/reject buttons for managers/HR, cancel for employee,
// status info, and attendance integration status.

frappe.ui.form.on("Work from Home Request", {
	refresh(frm) {
		if (frm.is_new()) return;

		const isHR =
			frappe.user_roles.includes("HR Manager") ||
			frappe.user_roles.includes("HR User") ||
			frappe.user_roles.includes("System Manager");

		// --- Status info ---
		const statusColors = {
			Open: "orange",
			Approved: "green",
			Rejected: "red",
			Cancelled: "darkgrey",
		};
		if (frm.doc.status) {
			frm.set_intro(
				`Status: ${frm.doc.status}` +
					(frm.doc.approved_by ? ` — Approved by ${frm.doc.approved_by}` : "") +
					(frm.doc.rejected_by ? ` — Rejected by ${frm.doc.rejected_by}` : ""),
				statusColors[frm.doc.status] || "blue"
			);
		}

		// --- Attendance info ---
		if (frm.doc.attendance_marked) {
			frm.set_intro(
				`Attendance has been marked for: ${frm.doc.attendance_dates || "all dates"}`,
				"green"
			);
		}

		// --- Manager/HR actions (only for Open requests) ---
		if (frm.doc.status === "Open" && isHR) {
			frm.add_custom_button(
				"Approve",
				() => {
					frappe.confirm(
						`Approve WFH for ${frm.doc.employee_name} from ${frm.doc.from_date} to ${frm.doc.to_date}?` +
							"\n\nThis will create Attendance records marked as Present for each WFH date.",
						() => {
							frappe.call({
								method: "elemental_erp.api.approve_wfh",
								args: { wfh_request: frm.doc.name },
								callback: (r) => {
									if (r.message) {
										frappe.show_alert("WFH Approved — Attendance marked.");
										frm.reload_doc();
									}
								},
							});
						}
					);
				},
				"Actions"
			).addClass("btn-success");

			frm.add_custom_button(
				"Reject",
				() => {
					frappe.prompt(
						{
							fieldname: "reason",
							label: "Rejection Reason",
							fieldtype": "Small Text",
							reqd: 1,
						},
						(values) => {
							frappe.call({
								method: "elemental_erp.api.reject_wfh",
								args: {
									wfh_request: frm.doc.name,
									reason: values.reason,
								},
								callback: () => {
									frappe.show_alert("WFH Rejected.");
									frm.reload_doc();
								},
							});
						},
						"Reject WFH Request"
					);
				},
				"Actions"
			).addClass("btn-danger");
		}

		// --- Employee cancel (only for Open requests, only if employee owns it) ---
		if (
			frm.doc.status === "Open" &&
			frm.doc.employee &&
			!isHR
		) {
			// Check if current user is the employee
			frappe.db.get_value(
				"Employee",
				{ user_id: frappe.session.user, name: frm.doc.employee },
				"name",
				(r) => {
					if (r && r.name) {
						frm.add_custom_button(
							"Cancel Request",
							() => {
								frappe.confirm(
									"Cancel this WFH request?",
									() => {
										frappe.call({
											method: "elemental_erp.api.cancel_wfh",
											args: { wfh_request: frm.doc.name },
											callback: () => {
												frappe.show_alert("WFH Request cancelled.");
												frm.reload_doc();
											},
										});
									}
								);
							},
							"Actions"
						).addClass("btn-default");
					}
				}
			);
		}

		// --- View Attendance ---
		if (frm.doc.attendance_marked && frm.doc.employee) {
			frm.add_custom_button(
				"View Attendance",
				() => {
					frappe.set_route("List", "Attendance", {
						employee: frm.doc.employee,
						attendance_date: ["between", [frm.doc.from_date, frm.doc.to_date]],
					});
				},
				"View"
			);
		}
	},

	// Auto-compute total days when dates change
	from_date(frm) {
		_compute_days(frm);
	},
	to_date(frm) {
		_compute_days(frm);
	},
});

function _compute_days(frm) {
	if (frm.doc.from_date && frm.doc.to_date) {
		const from = frappe.datetime.str_to_obj(frm.doc.from_date);
		const to = frappe.datetime.str_to_obj(frm.doc.to_date);
		const diff = Math.ceil((to - from) / (1000 * 60 * 60 * 24)) + 1;
		if (diff > 0) {
			frm.set_value("total_days", diff);
		}
	}
}
