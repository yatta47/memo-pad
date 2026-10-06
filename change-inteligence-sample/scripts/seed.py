#!/usr/bin/env python3
"""One-shot seed entrypoint (runs inside the backend image: `docker compose run --rm seed`)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.seed import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
