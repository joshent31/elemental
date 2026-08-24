"""Standalone regression tests for authenticated mobile scan access."""

import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
import zipfile


APP_ROOT = Path(__file__).resolve().parents[2]
ACCESS_PATH = APP_ROOT / "utils" / "mobile_access.py"
ANDROID_ROOT = APP_ROOT.parent / "mobile" / "android"


class FakeRedirect(Exception):
	pass


class FakePermissionError(Exception):
	pass


def load_access(*, user="operator@example.com", roles=(), path="/scan-menu"):
	frappe = types.ModuleType("frappe")
	frappe.session = types.SimpleNamespace(user=user)
	frappe.local = types.SimpleNamespace(
		flags=types.SimpleNamespace(),
		request=types.SimpleNamespace(full_path=path),
	)
	frappe.Redirect = FakeRedirect
	frappe.PermissionError = FakePermissionError
	frappe.get_roles = Mock(return_value=list(roles))

	def throw(message, exc_type):
		raise exc_type(message)

	frappe.throw = throw
	spec = importlib.util.spec_from_file_location("test_mobile_access_isolated", ACCESS_PATH)
	module = importlib.util.module_from_spec(spec)
	with patch.dict(sys.modules, {"frappe": frappe}):
		spec.loader.exec_module(module)
	return module, frappe


class TestMobilePageAccess(unittest.TestCase):
	def test_guest_is_redirected_to_login_and_back_to_requested_page(self):
		access, frappe = load_access(user="Guest", path="/gate-scan?qr=ABC")
		with self.assertRaises(FakeRedirect):
			access.require_mobile_page("/gate-scan", *access.GATE_SCAN_ROLES)
		self.assertEqual(
			frappe.local.flags.redirect_location,
			"/login?redirect-to=%2Fgate-scan%3Fqr%3DABC",
		)

	def test_assigned_role_can_open_its_page(self):
		access, _ = load_access(roles=["Elemental HR Gate User"])
		roles = access.require_mobile_page("/gate-scan", *access.GATE_SCAN_ROLES)
		self.assertIn("Elemental HR Gate User", roles)

	def test_unassigned_user_is_rejected(self):
		access, _ = load_access(roles=["Elemental Sales User"])
		with self.assertRaises(FakePermissionError):
			access.require_mobile_page("/gate-scan", *access.GATE_SCAN_ROLES)

	def test_production_menu_only_enables_assigned_area(self):
		access, _ = load_access(roles=["Elemental Packaging User"])
		menu = access.production_menu_access(["Elemental Packaging User"])
		self.assertTrue(menu["packaging"])
		self.assertFalse(menu["design"])
		self.assertFalse(menu["dispatch"])

	def test_unified_menu_includes_only_assigned_production_and_gate_areas(self):
		access, _ = load_access(roles=["Elemental QC User", "Elemental HR Gate User"])
		menu = access.mobile_app_access(["Elemental QC User", "Elemental HR Gate User"])
		self.assertTrue(menu["qc"])
		self.assertTrue(menu["gate"])
		self.assertFalse(menu["design"])
		self.assertFalse(menu["production"])


class TestMobileRoutesAreProtected(unittest.TestCase):
	def test_each_scan_page_controller_has_a_role_gate(self):
		for route in (
			"mobile_app",
			"scan_menu",
			"design_scan",
			"qc_scan",
			"process_scan",
			"transfer_out",
			"transfer_in",
			"pack_box",
			"dispatch_scan",
			"site_scan",
			"gate_scan",
		):
			with self.subTest(route=route):
				source = (APP_ROOT / "templates" / "pages" / f"{route}.py").read_text(encoding="utf-8")
				self.assertIn("require_mobile_page(", source)

	def test_sensitive_lookup_apis_are_not_guest_whitelisted(self):
		source = (APP_ROOT / "api.py").read_text(encoding="utf-8")
		for function_name in ("lookup_box", "lookup_qc_inspection", "lookup_design_task"):
			with self.subTest(function=function_name):
				marker = f"@frappe.whitelist(allow_guest=True)\ndef {function_name}"
				self.assertNotIn(marker, source)

	def test_mobile_api_entry_points_have_server_side_role_guards(self):
		tree = ast.parse((APP_ROOT / "api.py").read_text(encoding="utf-8"))
		functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
		for function_name in (
			"scan_qr",
			"lookup_subpart_label",
			"complete_subpart_process",
			"lookup_part_qr",
			"create_transfer",
			"get_transfer",
			"receive_transfer",
			"get_department_job_summary",
			"close_department",
			"lookup_box",
			"map_part_to_box",
			"get_or_create_dispatch_entry",
			"get_job_box_progress",
			"scan_box_dispatch",
			"scan_box_received",
			"scan_box_installed",
			"confirm_job_installation_complete",
			"lookup_qc_inspection",
			"record_qc_result",
			"lookup_design_task",
			"start_design",
			"complete_design",
			"lookup_employee_qr",
			"gate_scan",
		):
			with self.subTest(function=function_name):
				calls = [
					node
					for node in ast.walk(functions[function_name])
					if isinstance(node, ast.Call)
					and isinstance(node.func, ast.Name)
					and node.func.id == "_require_roles"
				]
				self.assertTrue(calls, f"{function_name} must enforce a mobile role")


class TestAndroidMobileWrappers(unittest.TestCase):
	def test_universal_app_has_no_compiled_customer_url(self):
		build = (ANDROID_ROOT / "app" / "build.gradle").read_text(encoding="utf-8")
		activity = (
			ANDROID_ROOT
			/ "app"
			/ "src"
			/ "main"
			/ "java"
			/ "com"
			/ "elementalfixtures"
			/ "mobile"
			/ "MainActivity.java"
		).read_text(encoding="utf-8")
		self.assertIn('private static final String START_PATH = "/mobile-app"', activity)
		self.assertNotIn("BASE_URL", build)
		self.assertNotIn("efpl-4.local", build)
		self.assertIn('private static final String SITE_URL_KEY = "site_url"', activity)
		self.assertIn("normaliseSiteUrl", activity)
		self.assertIn("changeSiteButton.setText(R.string.change_site)", activity)

	def test_wrapper_requests_camera_and_contains_navigation(self):
		manifest = (ANDROID_ROOT / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
		activity = (
			ANDROID_ROOT
			/ "app"
			/ "src"
			/ "main"
			/ "java"
			/ "com"
			/ "elementalfixtures"
			/ "mobile"
			/ "MainActivity.java"
		).read_text(encoding="utf-8")
		self.assertIn("android.permission.INTERNET", manifest)
		self.assertIn("android.permission.CAMERA", manifest)
		self.assertIn("isTrustedOrigin(request.getOrigin())", activity)
		self.assertIn("PermissionRequest.RESOURCE_VIDEO_CAPTURE", activity)
		self.assertIn('addJavascriptInterface(new ScannerBridge(), "ElementalAndroid")', activity)
		self.assertIn("if (isCurrentPageTrusted())", activity)
		self.assertIn("JSONObject.quote(value)", activity)

	def test_checked_in_universal_apk_has_android_payload(self):
		with zipfile.ZipFile(APP_ROOT / "public" / "apk" / "Elemental-Mobile.apk") as apk:
			self.assertIn("AndroidManifest.xml", apk.namelist())
			self.assertIn("classes.dex", apk.namelist())


class TestMobilePwa(unittest.TestCase):
	def test_unified_manifest_starts_at_role_aware_dashboard(self):
		manifest = (APP_ROOT / "www" / "manifest-mobile.json").read_text(encoding="utf-8")
		self.assertIn('"start_url": "/mobile-app"', manifest)

	def test_service_worker_never_caches_pages_or_api_responses(self):
		worker = (APP_ROOT / "www" / "sw.js").read_text(encoding="utf-8")
		self.assertIn('requestUrl.pathname.startsWith("/assets/elemental_erp/")', worker)
		self.assertIn("if (!isStaticElementalAsset) return;", worker)
		self.assertNotIn("catch(() => caches.match", worker)


if __name__ == "__main__":
	unittest.main()
