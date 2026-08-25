const elemental_fg_process_fields = [
	["process_metal", "Metal"],
	["process_wood", "Wood"],
	["process_electrical", "Electrical"],
	["process_powdercoating", "Powdercoating"],
	["process_paint", "Paint"],
	["process_us_assembly", "US Assembly"],
	["process_packing", "Packing"],
];

function elemental_update_fg_process_flow(cdt, cdn) {
	const row = locals[cdt][cdn];
	const selected = elemental_fg_process_fields
		.filter(([fieldname]) => Boolean(row[fieldname]))
		.map(([, label]) => label);
	frappe.model.set_value(cdt, cdn, "process_flow", selected.join(" → "));
	frappe.model.set_value(cdt, cdn, "processes", selected.join("\n"));
}

const elemental_fg_process_handlers = {};
for (const [fieldname] of elemental_fg_process_fields) {
	elemental_fg_process_handlers[fieldname] = (_frm, cdt, cdn) => {
		elemental_update_fg_process_flow(cdt, cdn);
	};
}

elemental_fg_process_handlers.subparts_add = (_frm, cdt, cdn) => {
	const row = locals[cdt][cdn];
	if (row.part_code) return;
	frappe.call({
		method:
			"elemental_erp.elemental_erp.doctype.finished_good.finished_good.get_next_part_code",
		callback: (response) => {
			if (response.message && !locals[cdt][cdn].part_code) {
				frappe.model.set_value(cdt, cdn, "part_code", response.message);
			}
		},
	});
};

frappe.ui.form.on("FG Subpart", elemental_fg_process_handlers);
