function update_salary_package_row(frm, cdt, cdn, source) {
	const row = locals[cdt][cdn];
	if (source === "annual_amount" || row.amount_basis === "Annual") {
		frappe.model.set_value(cdt, cdn, "monthly_amount", flt(row.annual_amount) / 12);
	} else {
		frappe.model.set_value(cdt, cdn, "annual_amount", flt(row.monthly_amount) * 12);
	}
	calculate_package_preview(frm);
}

function calculate_package_preview(frm) {
	if (frm.doctype !== "Employee Salary Package") return;
	const totals = { Earning: 0, Deduction: 0, "Employer Contribution": 0 };
	(frm.doc.components || []).forEach((row) => {
		if (!row.enabled) return;
		totals[row.treatment] = flt(totals[row.treatment]) + flt(row.monthly_amount);
	});
	frm.set_value("monthly_earnings", totals.Earning);
	frm.set_value("monthly_deductions", totals.Deduction);
	frm.set_value("monthly_take_home", totals.Earning - totals.Deduction);
	frm.set_value("monthly_employer_contribution", totals["Employer Contribution"]);
	frm.set_value("monthly_ctc", totals.Earning + totals["Employer Contribution"]);
	const annualCtc = (frm.doc.components || [])
		.filter((row) => ["Earning", "Employer Contribution"].includes(row.treatment))
		.filter((row) => row.enabled)
		.reduce((total, row) => total + flt(row.annual_amount), 0);
	frm.set_value("annual_ctc", annualCtc);
}

function sort_salary_components(frm) {
	const priority = {
		"basic": 10,
		"house rent allowance": 20,
		"hra": 20,
		"dearness allowance": 30,
		"da": 30,
		"provident fund": 1010,
		"pf": 1010,
		"epf": 1010,
		"esic": 1020,
		"esi": 1020,
		"professional tax": 1030,
		"pt": 1030,
		"income tax": 1040,
	};
	const rank = (row) => {
		const name = (row.salary_component || "").trim().toLowerCase();
		const group = row.treatment === "Earning" ? 0 : row.treatment === "Deduction" ? 1000 : 2000;
		return [priority[name] === undefined ? group + 100 : priority[name], name];
	};
	(frm.doc.components || []).sort((a, b) => {
		const left = rank(a), right = rank(b);
		return left[0] - right[0] || left[1].localeCompare(right[1]);
	});
	(frm.doc.components || []).forEach((row, index) => { row.idx = index + 1; });
}

function load_salary_component_catalogue(frm) {
	return frappe.call({
		method: "elemental_erp.elemental_erp.doctype.employee_salary_package.employee_salary_package.get_salary_component_catalogue",
		freeze: true,
		freeze_message: __("Loading salary components..."),
		callback: (r) => {
			const existing = new Set((frm.doc.components || []).map((row) => row.salary_component));
			(r.message || []).forEach((component) => {
				if (existing.has(component.salary_component)) return;
				const row = frm.add_child("components");
				row.enabled = 0;
				row.salary_component = component.salary_component;
				row.treatment = component.treatment;
				row.automatic_calculation = component.automatic_calculation;
				row.amount_basis = "Monthly";
			});
			sort_salary_components(frm);
			frm.refresh_field("components");
		},
	});
}

frappe.ui.form.on("Employee Salary Package", {
	onload(frm) {
		if (frm.is_new() && !(frm.doc.components || []).length) {
			load_salary_component_catalogue(frm);
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Refresh Salary Components"), () => load_salary_component_catalogue(frm));
		}
	},
});

frappe.ui.form.on("Salary Package Component", {
	salary_component(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.salary_component) return;
		frappe.db.get_value(
			"Salary Component",
			row.salary_component,
			["type", "salary_component_abbr"],
			(r) => {
				if (!r) return;
				const abbr = (r.salary_component_abbr || "").trim().toUpperCase();
				frappe.model.set_value(cdt, cdn, "treatment", r.type);
				frappe.model.set_value(cdt, cdn, "automatic_calculation", ["PF", "EPF", "ESI", "ESIC", "PT"].includes(abbr) ? 1 : 0);
			}
		);
	},
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const grid_row = frm.fields_dict.components.grid.grid_rows_by_docname[cdn];
		if (grid_row) {
			grid_row.toggle_editable("monthly_amount", !row.automatic_calculation);
			grid_row.toggle_editable("annual_amount", !row.automatic_calculation);
			grid_row.toggle_editable("amount_basis", !row.automatic_calculation);
		}
	},
	enabled(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.enabled) {
			frappe.model.set_value(cdt, cdn, "monthly_amount", 0);
			frappe.model.set_value(cdt, cdn, "annual_amount", 0);
		}
		calculate_package_preview(frm);
	},
	monthly_amount(frm, cdt, cdn) {
		if (locals[cdt][cdn].amount_basis !== "Annual") update_salary_package_row(frm, cdt, cdn, "monthly_amount");
	},
	annual_amount(frm, cdt, cdn) {
		if (locals[cdt][cdn].amount_basis === "Annual") update_salary_package_row(frm, cdt, cdn, "annual_amount");
	},
	amount_basis(frm, cdt, cdn) {
		update_salary_package_row(frm, cdt, cdn, locals[cdt][cdn].amount_basis === "Annual" ? "annual_amount" : "monthly_amount");
	},
	treatment(frm) {
		calculate_package_preview(frm);
	},
	components_remove(frm) {
		calculate_package_preview(frm);
	},
});
