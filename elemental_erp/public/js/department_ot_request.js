frappe.ui.form.on("Department OT Request", {
	setup(frm) {
		frm.set_query("employee", "employees", () => ({
			filters: { status: "Active", department: frm.doc.department || "" },
		}));
	},
	department(frm) {
		if (frm.doc.employees && frm.doc.employees.length) {
			frappe.confirm("Changing Department will clear the selected workers.", () => {
				frm.clear_table("employees");
				frm.refresh_field("employees");
			});
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.status !== "Sent to HR") return;
		if (!(frappe.user_roles.includes("Elemental HR Gate HOD") || frappe.user_roles.includes("System Manager"))) return;
		frm.add_custom_button("Approve OT Request", () => {
			frappe.prompt({fieldname:"remarks",label:"HR Remarks",fieldtype:"Small Text"}, (values) => {
				frappe.call({method:"elemental_erp.elemental_erp.doctype.department_ot_request.department_ot_request.approve_ot_request",args:{name:frm.doc.name,remarks:values.remarks},callback:()=>frm.reload_doc()});
			}, "Approve OT Request");
		}).addClass("btn-primary");
		frm.add_custom_button("Reject OT Request", () => {
			frappe.prompt({fieldname:"remarks",label:"Rejection Reason",fieldtype:"Small Text",reqd:1}, (values) => {
				frappe.call({method:"elemental_erp.elemental_erp.doctype.department_ot_request.department_ot_request.reject_ot_request",args:{name:frm.doc.name,remarks:values.remarks},callback:()=>frm.reload_doc()});
			}, "Reject OT Request");
		});
	},
});
