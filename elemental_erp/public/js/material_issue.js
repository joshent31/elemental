frappe.ui.form.on("Material Issue", {
	setup(frm) {
		frm.set_query("material_indent", () => {
			const filters = { docstatus: 1 };
			if (frm.doc.job) {
				filters.job = frm.doc.job;
			}
			return { filters };
		});
	},

	material_indent(frm) {
		if (!frm.doc.material_indent) {
			return;
		}
		frappe.db.get_value(
			"Material Indent",
			frm.doc.material_indent,
			["job", "department"]
		).then(({ message }) => {
			if (message) {
				return frm.set_value({
					job: message.job,
					department: message.department,
				});
			}
		});
	},
});
