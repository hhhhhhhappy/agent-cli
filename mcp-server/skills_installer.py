from __future__ import print_function

import argparse
import os
import shutil
import sys
import tempfile

import external_mcp_server.skills as skills_package


DEFAULT_DESTINATION = os.path.join("~", ".claude", "skills")


class InstallError(Exception):
    """Raised when bundled skill installation fails."""


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Install bundled skill assets from this package."
    )
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser(
        "install",
        help="Install all bundled skills into the destination directory.",
    )
    install_parser.add_argument(
        "--dest",
        default=DEFAULT_DESTINATION,
        help=(
            "Destination skills directory. Defaults to {0}.".format(DEFAULT_DESTINATION)
        ),
    )

    options = parser.parse_args(argv)
    if options.command is None:
        parser.error("a subcommand is required")
    return options


def resolve_destination(dest):
    return os.path.abspath(os.path.expanduser(dest))


def get_bundled_skills_root(package=skills_package):
    package_file = getattr(package, "__file__", None)
    if not package_file:
        raise InstallError("Unable to resolve bundled skills package path")
    return os.path.dirname(os.path.abspath(package_file))


def discover_bundled_skills(package=skills_package):
    skills_root = get_bundled_skills_root(package=package)
    skills = []
    for entry in sorted(os.listdir(skills_root)):
        source_dir = os.path.join(skills_root, entry)
        if entry.startswith(".") or entry == "__pycache__":
            continue
        if not os.path.isdir(source_dir):
            continue
        if not os.path.exists(os.path.join(source_dir, "SKILL.md")):
            continue
        skills.append((entry, source_dir))

    if not skills:
        raise InstallError("No bundled skills found in {0}".format(skills_root))
    return skills


def _prepare_destination(dest):
    if os.path.exists(dest) and not os.path.isdir(dest):
        raise InstallError("Destination is not a directory: {0}".format(dest))

    parent_dir = os.path.dirname(dest)
    if parent_dir and not os.path.isdir(parent_dir):
        os.makedirs(parent_dir)


def install_bundled_skills(dest=DEFAULT_DESTINATION, package=skills_package):
    resolved_dest = resolve_destination(dest)
    bundled_skills = discover_bundled_skills(package=package)

    _prepare_destination(resolved_dest)

    conflicts = []
    for skill_name, _source_dir in bundled_skills:
        destination_dir = os.path.join(resolved_dest, skill_name)
        if os.path.exists(destination_dir):
            conflicts.append(destination_dir)

    if conflicts:
        raise InstallError("Skill already exists: {0}".format(conflicts[0]))

    staging_parent = os.path.dirname(resolved_dest) or None
    staging_root = tempfile.mkdtemp(prefix="agent-cli-skills-", dir=staging_parent)

    try:
        for skill_name, source_dir in bundled_skills:
            staged_dir = os.path.join(staging_root, skill_name)
            shutil.copytree(source_dir, staged_dir)

        if not os.path.isdir(resolved_dest):
            os.makedirs(resolved_dest)

        installed = []
        for skill_name, _source_dir in bundled_skills:
            staged_dir = os.path.join(staging_root, skill_name)
            destination_dir = os.path.join(resolved_dest, skill_name)
            shutil.move(staged_dir, destination_dir)
            installed.append(skill_name)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return {
        "dest": resolved_dest,
        "skills": installed,
    }


def print_install_summary(result, stream=None):
    stream = stream or sys.stdout
    stream.write("Installed bundled skills into {0}\n".format(result["dest"]))
    for skill_name in result["skills"]:
        stream.write("- {0}\n".format(skill_name))


def main(argv=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    argv = argv if argv is not None else sys.argv[1:]

    try:
        options = parse_args(argv)
        if options.command != "install":
            raise InstallError("Unsupported command: {0}".format(options.command))

        result = install_bundled_skills(dest=options.dest)
        print_install_summary(result, stream=stdout)
        return 0
    except InstallError as exc:
        stderr.write("Error: {0}\n".format(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
