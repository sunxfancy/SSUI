"""Collect PEP 508 requirements; uv solves intersections and reports conflicts."""
import argparse
from pathlib import Path
import sys
from packaging.requirements import Requirement
import yaml

ROOT = Path(__file__).resolve().parent.parent

def collect(target: str) -> str:
    source = ROOT / "dependencies" / f"requirements-{target}.txt"
    if not source.is_file():
        raise ValueError(f"Unknown dependency target: {target}")
    lines = [f"# Target: {target}; Python 3.12", f"# Source: {source.relative_to(ROOT)}"]
    for number, raw in enumerate(source.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(("--extra-index-url ", "--index-url ", "-r ", "-c ")):
            try:
                Requirement(line)
            except Exception as exc:
                raise ValueError(f"{source}:{number}: {exc}") from exc
        lines.append(line)
    for manifest in sorted((ROOT / "extensions").glob("*/ssextension.yaml")):
        config = yaml.safe_load(manifest.read_text()) or {}
        server = config.get("server") or {}
        if server.get("venv", "shared") != "shared":
            continue
        lines.append(f"\n# Source: {manifest.relative_to(ROOT)}")
        for requirement in server.get("dependencies", []):
            Requirement(requirement)
            lines.append(requirement)
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = collect(args.target)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    else:
        sys.stdout.write(result)

if __name__ == "__main__":
    main()
