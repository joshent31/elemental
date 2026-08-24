frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		frm.set_query("elemental_material_indent", () => ({
			filters: {
				docstatus: 1,
				...(frm.doc.elemental_job ? { job: frm.doc.elemental_job } : {}),
			},
		}));
	},

	elemental_material_indent(frm) {
		if (!frm.doc.elemental_material_indent) return;
		frappe.db.get_value("Material Indent", frm.doc.elemental_material_indent, "job").then((r) => {
			const job = r.message && r.message.job;
			if (job) frm.set_value("elemental_job", job);
		});
	},
});
