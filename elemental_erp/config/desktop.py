from frappe import _


def get_data():
	return [
		{
			"module_name": "Elemental ERP",
			"category": "Modules",
			"label": _("Elemental ERP"),
			"color": "#2e7d32",
			"icon": "octicon octicon-package",
			"type": "module",
			"description": "Job -> Purchase -> Production -> Packaging -> Dispatch tracking with QR codes",
		}
	]
