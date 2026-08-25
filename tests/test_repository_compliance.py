from __future__ import annotations

import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RepositoryComplianceTests(unittest.TestCase):
    def test_license_identifies_copyright_holder(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Michael Kurath", license_text)

    def test_python_metadata_declares_mit(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            metadata = tomllib.load(handle)
        self.assertEqual(metadata["project"]["license"], "MIT")
        self.assertEqual(metadata["project"]["authors"], [{"name": "Michael Kurath"}])

    def test_security_policy_documents_network_boundary(self) -> None:
        policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("do not expose port `8080` to the internet", policy)
        self.assertIn("independently revocable", policy)

    def test_third_party_notice_covers_bundled_model_and_firmware(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("haarcascade_frontalface_default.xml", notices)
        self.assertIn("Arduino core for ESP32", notices)
        self.assertIn("LGPL-2.1-or-later", notices)

    def test_real_firmware_secrets_remain_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("firmware/ee02_photo_frame/secrets.h", ignore)
        self.assertIn("firmware/ee04_photo_frame/secrets.h", ignore)


if __name__ == "__main__":
    unittest.main()
