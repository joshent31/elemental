import frappe

from elemental_erp.utils.mobile_access import MOBILE_APP_ROLES, mobile_app_access, require_mobile_page


def get_context(context):
	roles = require_mobile_page("/mobile-app", *MOBILE_APP_ROLES)
	context.no_cache = 1
	for area, allowed in mobile_app_access(roles).items():
		setattr(context, f"can_{area}", allowed)
	context.head_include = """
<link rel="manifest" href="/manifest-mobile.json">
<meta name="theme-color" content="#1a2942">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Elemental Mobile">
<link rel="apple-touch-icon" href="/assets/elemental_erp/icons/icon-192.png">
<script>
if ('serviceWorker' in navigator) {
	navigator.serviceWorker.register('/sw.js');
}
</script>
"""
	return context
