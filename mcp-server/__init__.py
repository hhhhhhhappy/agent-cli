"""External MCP server package for device CLI bridging."""

from __future__ import absolute_import

import os


_PACKAGE_DIR = os.path.dirname(os.path.realpath(__file__))
_REPO_ROOT = os.path.dirname(_PACKAGE_DIR)
_SKILLS_SOURCE_DIR = os.path.join(_REPO_ROOT, "skills")

# Allow source-tree imports of ``external_mcp_server.skills`` when tests expose
# only the ``mcp-server`` directory on ``PYTHONPATH``.
if os.path.isdir(_SKILLS_SOURCE_DIR) and _REPO_ROOT not in __path__:
    __path__.append(_REPO_ROOT)
