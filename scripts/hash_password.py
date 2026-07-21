#!/usr/bin/env python3
"""Generate a value for HOUSEHOLD_PASSWORD_HASH_B64 in .env.

Usage:
    python scripts/hash_password.py "your-chosen-password"

Prints a base64-encoded bcrypt hash. It's base64-encoded (rather than the raw
"$2b$12$..." hash) because raw bcrypt hashes contain "$" characters that Docker
Compose's .env parser tries to interpolate as variable references.
"""

import base64
import sys

import bcrypt


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/hash_password.py <password>", file=sys.stderr)
        sys.exit(1)
    hashed = bcrypt.hashpw(sys.argv[1].encode("utf-8"), bcrypt.gensalt())
    print(base64.b64encode(hashed).decode("utf-8"))


if __name__ == "__main__":
    main()
