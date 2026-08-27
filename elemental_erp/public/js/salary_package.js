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
		totals[row.treatment] = flt(totals[row.treatment]) + flt(row.monthly_amount);
	});
	frm.set_value("monthly_earnings", totals.Earning);
	frm.set_value("monthly_deductions", totals.Deduction);
	frm.set_value("monthly_take_home", totals.Earning - totals.Deduction);
	frm.set_value("monthly_employer_contribution", totals["Employer Contribution"]);
	frm.set_value("monthly_ctc", totals.Earning + totals["Employer Contribution"]);
	const annualCtc = (frm.doc.components || [])
		.filter((row) => ["Earning", "Employer Contribution"].includes(row.treatment))
		.reduce((total, row) => total + flt(row.annual_amount), 0);
	frm.set_value("annual_ctc", annualCtc);
}

frappe.ui.form.on("Salary Package Component", {
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
