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

    def test_runtime_dependencies_have_one_shared_definition(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            metadata = tomllib.load(handle)
        requirements = [
            line.strip()
            for line in (ROOT / "epaper_photo_frame" / "requirements.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertEqual(metadata["project"]["dependencies"], requirements)

        dockerfile = (ROOT / "epaper_photo_frame" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        self.assertIn("-r /tmp/requirements.txt", dockerfile)
        for package in ("fastapi~=", "Pillow~=", "uvicorn~="):
            self.assertNotIn(package, dockerfile)

    def test_release_versions_stay_in_sync(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            package_version = tomllib.load(handle)["project"]["version"]
        config = (ROOT / "epaper_photo_frame" / "config.yaml").read_text(
            encoding="utf-8"
        )
        dockerfile = (ROOT / "epaper_photo_frame" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        package_init = (
            ROOT / "epaper_photo_frame" / "app" / "frame_app" / "__init__.py"
        ).read_text(encoding="utf-8")
        main = (
            ROOT / "epaper_photo_frame" / "app" / "frame_app" / "main.py"
        ).read_text(encoding="utf-8")
        self.assertIn(f'version: "{package_version}"', config)
        self.assertIn(f"ARG BUILD_VERSION={package_version}", dockerfile)
        self.assertIn(f'__version__ = "{package_version}"', package_init)
        self.assertIn(f'version="{package_version}"', main)

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
