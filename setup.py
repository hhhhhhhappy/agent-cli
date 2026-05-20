from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).resolve().parent


setup(
    name="agent-mcp",
    version="0.1.0",
    description="MCP server that bridges remote device agent_cli commands over SSH.",
    long_description=(ROOT / "mcp-server" / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    python_requires=">=3.6",
    packages=["external_mcp_server", "external_mcp_server.skills"],
    package_dir={
        "external_mcp_server": "mcp-server",
        "external_mcp_server.skills": "skills",
    },
    include_package_data=True,
    package_data={
        "external_mcp_server": ["config/*"],
        "external_mcp_server.skills": ["*", "*/*", "*/*/*", "*/*/*/*"],
    },
    entry_points={
        "console_scripts": [
            "agent-mcp=external_mcp_server.server:main",
            "agent-cli-skills=external_mcp_server.skills_installer:main",
            "agent-cli-claude-skills=external_mcp_server.skills_installer:main",
        ],
    },
)
