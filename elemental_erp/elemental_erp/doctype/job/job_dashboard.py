from frappe import _


def get_data():
	"""Show every transaction that is linked back to this Job."""
	return {
		"fieldname": "job",
		"non_standard_fieldnames": {
			"Purchase Order": "elemental_job",
			"Sales Invoice": "elemental_job",
			"Virtual FG Transfer": "source_job",
			"Virtual FG Reservation": "target_job",
		},
		"transactions": [
			{
				"label": _("Design & Quality"),
				"items": ["Design Task", "Data Entry Task", "QC Inspection"],
			},
			{
				"label": _("Production Tracking"),
				"items": [
					"Job Subpart Label",
					"QR Code Master",
					"QR Scan Log",
					"Production Entry",
					"Worker Job Time Log",
					"Department Transfer",
					"Job Department Status",
				],
			},
			{
				"label": _("Material & Purchase"),
				"items": [
					"Material Indent",
					"Material Issue",
					"Purchase Order",
					"Job Material Consumption",
				],
			},
			{
				"label": _("Packaging & Dispatch"),
				"items": ["Packaging Entry", "Packing Box", "Dispatch Entry", "Virtual FG Transfer", "Virtual FG Reservation"],
			},
			{"label": _("Audit"), "items": ["Job FG Change Log"]},
			{
				"label": _("Sales & Billing"),
				"items": ["Elemental Quotation", "Sales Invoice"],
			},
		],
	}
