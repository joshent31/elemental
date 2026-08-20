// Client script for Leave Application form.
// Warns if "Saturday Off" is applied on a non-Saturday.

frappe.ui.form.on("Leave Application", {
	from_date(frm) {
		_check_saturday_off(frm);
	},
	leave_type(frm) {
		_check_saturday_off(frm);
	},
});

function _check_saturday_off(frm) {
	if (frm.doc.leave_type === "Saturday Off" && frm.doc.from_date) {
		const date = frappe.datetime.str_to_obj(frm.doc.from_date);
		const day = date.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
		if (day !== 6) {
			const dayName = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][day];
			frm.set_intro(
				`⚠️ "Saturday Off" can only be applied on Saturdays. You selected ${dayName}. ` +
				`Please change the date to a Saturday.`,
				"red"
			);
		} else {
			frm.set_intro(
				`✅ "Saturday Off" — ${frm.doc.from_date} is a Saturday. Good to go!`,
				"green"
			);
		}
	}
}
