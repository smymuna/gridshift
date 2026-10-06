"""Print the API's OpenAPI document. The web app generates its TypeScript types from it.

python -m gridshift.openapi > ../../packages/api-client/openapi.json
"""

from __future__ import annotations

import json
import sys

from gridshift.api.app import create_app
from gridshift.config import Settings


def main() -> None:
    spec = create_app(Settings()).openapi()
    json.dump(spec, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
