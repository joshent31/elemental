frappe.ui.form.on("Virtual FG Transfer", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.dashboard.set_headline("Submitting this document creates and submits a real ERPNext Material Transfer into the configured Virtual FG Warehouse.");
		}
	}
});
