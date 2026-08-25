"""Desktop/laptop webcam support on every Html5Qrcode scanner page."""

from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
PAGES = APP_ROOT / "templates" / "pages"
PUBLIC_JS = APP_ROOT / "public" / "js"


class TestDesktopQrCamera(unittest.TestCase):
	def test_shared_camera_helper_supports_selection_and_https_guidance(self):
		source = (PUBLIC_JS / "qr_camera.js").read_text(encoding="utf-8")
		self.assertIn("Html5Qrcode.getCameras()", source)
		self.assertIn("elemental_qr_camera_id", source)
		self.assertIn("Select Laptop / USB Camera", source)
		self.assertIn("using HTTPS", source)

	def test_all_html5_qrcode_pages_load_desktop_camera_helper(self):
		for page in PAGES.glob("*.html"):
			source = page.read_text(encoding="utf-8")
			if "html5-qrcode.min.js" not in source:
				continue
			with self.subTest(page=page.name):
				self.assertIn("/assets/elemental_erp/js/qr_camera.js", source)
				self.assertNotIn('{ facingMode: "environment" }', source)
				self.assertNotIn('{facingMode:"environment"}', source)


if __name__ == "__main__":
	unittest.main()
