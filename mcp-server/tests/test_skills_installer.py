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
        self.expected_skills = [
            name for name, _source_dir in installer.discover_bundled_skills()
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def relative_files(self, root):
        files = []
        for directory, _subdirs, filenames in os.walk(root):
            for filename in filenames:
                files.append(os.path.relpath(os.path.join(directory, filename), root))
        return sorted(files)

    def test_install_copies_bundled_skill_files(self):
        result = installer.install_bundled_skills(dest=self.dest_dir)
        self.assertEqual(result["skills"], self.expected_skills)

        skills_root = installer.get_bundled_skills_root()
        for skill_name in self.expected_skills:
            installed_dir = os.path.join(self.dest_dir, skill_name)
            source_dir = os.path.join(skills_root, skill_name)
            self.assertTrue(os.path.isdir(installed_dir))
            self.assertEqual(
                self.relative_files(installed_dir),
                self.relative_files(source_dir),
            )

    def test_install_expands_default_destination_from_home(self):
        home_dir = os.path.join(self.temp_dir, "home")
        expected_dest = os.path.join(home_dir, ".claude", "skills")

        with mock.patch.dict(os.environ, {"HOME": home_dir}, clear=False):
            result = installer.install_bundled_skills()

        self.assertEqual(result["dest"], expected_dest)
        for skill_name in self.expected_skills:
            self.assertTrue(os.path.isdir(os.path.join(expected_dest, skill_name)))

    def test_install_fails_when_skill_already_exists(self):
        existing_dir = os.path.join(self.dest_dir, self.expected_skills[0])
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

        exit_code = installer.main(["--dest", self.dest_dir], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        for skill_name in self.expected_skills:
            self.assertIn(skill_name, stdout.getvalue())

    def test_main_keeps_install_subcommand_compatible(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = installer.main(
            ["install", "--dest", self.dest_dir],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        for skill_name in self.expected_skills:
            self.assertIn(skill_name, stdout.getvalue())

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

    def test_discover_bundled_skills_supports_namespace_package_paths(self):
        package_root = os.path.join(self.temp_dir, "namespace-package")
        os.makedirs(package_root)
        skill_dir = os.path.join(package_root, "custom-skill")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as handle:
            handle.write("# custom skill\n")

        fake_package = SimpleNamespace(__file__=None, __path__=[package_root])

        skills = installer.discover_bundled_skills(package=fake_package)

        self.assertEqual(skills, [("custom-skill", skill_dir)])
