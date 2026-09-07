frappe.ui.form.on("Virtual FG Reservation", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && ["Reserved", "Partly Utilized"].includes(frm.doc.status)) {
			frm.add_custom_button("Move to Target Warehouse", () => {
				frappe.prompt([
					{fieldname:"qty",label:"Qty",fieldtype:"Float",reqd:1,default:frm.doc.reserved_qty-frm.doc.utilized_qty},
					{fieldname:"warehouse",label:"Target Warehouse",fieldtype:"Link",options:"Warehouse",reqd:1,default:frm.doc.target_warehouse}
				], values => frappe.call({method:"elemental_erp.utils.fg_change_management.utilize_virtual_stock",args:{reservation:frm.doc.name,qty:values.qty,target_warehouse:values.warehouse},freeze:true,callback:()=>frm.reload_doc()}), "Utilize Reserved Stock");
			}).addClass("btn-primary");
		}
	}
});
