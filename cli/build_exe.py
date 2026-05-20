from __future__ import print_function

import os
import sys


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        print(
            "PyInstaller is not installed. Install it first, for example: "
            "`py -3 -m pip install pyinstaller` on Windows.",
            file=sys.stderr,
        )
        return 1

    repo_root = _repo_root()
    entrypoint = os.path.join(repo_root, "cli", "cli.py")

    args = [
        "--clean",
        "--onefile",
        "--name",
        "agent-cli",
        "--paths",
        repo_root,
        entrypoint,
    ]

    PyInstaller.__main__.run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
