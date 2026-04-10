from __future__ import print_function

import io
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import external_mcp_server.skills_installer as installer


class SkillsInstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="skills-installer-test-")
        self.dest_dir = os.path.join(self.temp_dir, "installed-skills")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_install_copies_bundled_skill_files(self):
        result = installer.install_bundled_skills(dest=self.dest_dir)

        installed_dir = os.path.join(self.dest_dir, "device-diagnostics")
        self.assertEqual(result["skills"], ["device-diagnostics"])
        self.assertTrue(os.path.isdir(installed_dir))
        self.assertTrue(os.path.isfile(os.path.join(installed_dir, "SKILL.md")))
        self.assertTrue(
            os.path.isfile(os.path.join(installed_dir, "references", "connectivity.md"))
        )

    def test_install_expands_default_destination_from_home(self):
        home_dir = os.path.join(self.temp_dir, "home")
        expected_dest = os.path.join(home_dir, ".claude", "skills")

        with mock.patch.dict(os.environ, {"HOME": home_dir}, clear=False):
            result = installer.install_bundled_skills()

        self.assertEqual(result["dest"], expected_dest)
        self.assertTrue(os.path.isdir(os.path.join(expected_dest, "device-diagnostics")))

    def test_install_fails_when_skill_already_exists(self):
        existing_dir = os.path.join(self.dest_dir, "device-diagnostics")
        os.makedirs(existing_dir)
        marker_path = os.path.join(existing_dir, "marker.txt")
        with open(marker_path, "w") as handle:
            handle.write("keep me")

        with self.assertRaises(installer.InstallError) as context:
            installer.install_bundled_skills(dest=self.dest_dir)

        self.assertIn(existing_dir, str(context.exception))
        with open(marker_path, "r") as handle:
            self.assertEqual(handle.read(), "keep me")

    def test_main_reports_installed_skill_names(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = installer.main(["install", "--dest", self.dest_dir], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("device-diagnostics", stdout.getvalue())

    def test_discover_bundled_skills_uses_package_path(self):
        package_root = os.path.join(self.temp_dir, "alt-package")
        os.makedirs(package_root)
        init_path = os.path.join(package_root, "__init__.py")
        with open(init_path, "w") as handle:
            handle.write("# test package\n")

        skill_dir = os.path.join(package_root, "custom-skill")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as handle:
            handle.write("# custom skill\n")

        fake_package = SimpleNamespace(__file__=init_path)

        skills = installer.discover_bundled_skills(package=fake_package)

        self.assertEqual(skills, [("custom-skill", skill_dir)])
