"""Export the deterministic production HTTP schema for frontend type generation."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.contract_app import create_contract_app  # noqa: E402


OUTPUT = ROOT / "server" / "openapi.json"


def main() -> None:
    schema = create_contract_app().openapi()
    OUTPUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
