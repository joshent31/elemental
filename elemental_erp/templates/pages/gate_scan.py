import frappe

from elemental_erp.utils.mobile_access import GATE_SCAN_ROLES, require_mobile_page


def get_context(context):
	require_mobile_page("/gate-scan", *GATE_SCAN_ROLES)
	context.no_cache = 1
	context.head_include = """
<link rel="manifest" href="/manifest-gate.json">
<meta name="theme-color" content="#1a2942">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Elemental Gate">
<link rel="apple-touch-icon" href="/assets/elemental_erp/icons/icon-192.png">
<script>
if ('serviceWorker' in navigator) {
	navigator.serviceWorker.register('/sw.js');
}
</script>
"""
	return context
