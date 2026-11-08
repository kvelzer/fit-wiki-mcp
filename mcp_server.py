#!/usr/bin/env python3
"""Checkout launcher; credentials are resolved relative to this file, not the client's cwd."""

import os
from pathlib import Path

os.environ.setdefault("FITWIKI_ENV_FILE", str(Path(__file__).resolve().with_name(".env")))

from fitwiki_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
