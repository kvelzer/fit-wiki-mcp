#!/usr/bin/env python3
"""Print a client-specific config fragment. Never changes the client's configuration."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configuration(client: str, root: Path = ROOT) -> str:
    python = str(root / ".venv" / "bin" / "python")
    launcher = str(root / "mcp_server.py")
    common = {"command": python, "args": [launcher], "cwd": str(root)}
    if client == "codex":
        return "\n".join(
            [
                "[mcp_servers.fitwiki]",
                f"command = {json.dumps(python)}",
                f"args = [{json.dumps(launcher)}]",
                f"cwd = {json.dumps(str(root))}",
                "startup_timeout_sec = 20",
                "tool_timeout_sec = 120",
                "",
            ]
        )
    if client == "opencode":
        value = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "servers": {
                    "fitwiki": {
                        "type": "local",
                        "command": [python, launcher],
                        "cwd": str(root),
                        "protocol": "auto",
                        "timeout": {"startup": 30000, "catalog": 30000, "execution": 120000},
                    }
                }
            },
        }
    else:
        if client == "pi":
            common["timeout"] = 120
        elif client == "antigravity":
            common["timeoutSeconds"] = 120
        value = {"mcpServers": {"fitwiki": common}}
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=["codex", "claude", "opencode", "pi", "antigravity"])
    args = parser.parse_args()
    sys.stdout.write(configuration(args.client))
