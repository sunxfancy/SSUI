"""Audit index metadata without executing package build code or downloading wheels."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename
from packaging.version import InvalidVersion, Version


def wheel_matches(filename, tags):
    try:
        return bool(parse_wheel_filename(filename)[3] & tags)
    except ValueError:
        return False


def read_metadata(source):
    for attempt in range(3):
        try:
            with urlopen(Request(source, headers={"User-Agent": "SSUI-dependency-audit/1"}), timeout=40) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise


def audit(requirement, tags, python_version, extra_indexes=()):
    req = Requirement(requirement)
    result = {"requirement": requirement, "name": req.name}
    if req.url:
        filename = unquote(Path(urlparse(req.url).path).name)
        result.update(status="direct-wheel" if wheel_matches(filename, tags) else "incompatible-direct-url", source=req.url)
        return result
    source = f"https://pypi.org/pypi/{req.name}/json"
    result["source"] = source
    try:
        metadata = read_metadata(source)
        compatible = []
        sdists = []
        matched = []
        for version_string, files in metadata["releases"].items():
            try:
                version = Version(version_string)
            except InvalidVersion:
                continue
            # An explicit ==0.66b1 pin intentionally allows that prerelease.
            if version not in req.specifier:
                continue
            available = [f for f in files if not f.get("yanked") and (not f.get("requires_python") or Version(python_version) in SpecifierSet(f["requires_python"]))]
            if not available:
                continue
            matched.append(version)
            wheels = [f["filename"] for f in available if f["packagetype"] == "bdist_wheel" and wheel_matches(f["filename"], tags)]
            if wheels:
                compatible.append((version, wheels))
            if any(f["packagetype"] == "sdist" for f in available):
                sdists.append(version)
        # PyTorch Windows ARM64 CPU wheels are published on its official index,
        # rather than PyPI. Inspect links without downloading the wheel itself.
        for index in extra_indexes if not compatible else ():
            index_url = index.rstrip('/') + '/' + re.sub(r'[-_.]+', '-', req.name).lower() + '/'
            try:
                with urlopen(Request(index_url, headers={"User-Agent": "SSUI-dependency-audit/1"}), timeout=40) as response:
                    html = response.read().decode('utf-8')
                for filename in re.findall(r'>([^<>]+\.whl)<', html):
                    filename = unquote(filename)
                    try:
                        _, version, _, wheel_tags = parse_wheel_filename(filename)
                    except ValueError:
                        continue
                    if version in req.specifier and wheel_tags & tags:
                        compatible.append((version, [filename]))
                        result["source"] = index_url
            except Exception as error:
                result.setdefault("indexErrors", []).append({"index": index_url, "error": str(error)})
        if compatible:
            version, wheels = max(compatible)
            result.update(status="wheel", version=str(version), wheels=wheels)
        elif sdists:
            result.update(status="source-only", version=str(max(sdists)))
        else:
            result.update(status="no-compatible-distribution", latestMatching=str(max(matched)) if matched else None)
    except Exception as error:
        result.update(status="metadata-error", error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements")
    parser.add_argument("--platform", default="win_arm64")
    parser.add_argument("--python-version", default="3.12.8")
    parser.add_argument("--output", required=True)
    parser.add_argument("--extra-index-url", action="append", default=[])
    args = parser.parse_args()
    version = tuple(map(int, args.python_version.split(".")[:2]))
    tags = set(cpython_tags(version, platforms=[args.platform])) | set(compatible_tags(version, interpreter=f"cp{version[0]}{version[1]}", platforms=[args.platform]))
    lines = [line.strip() for line in Path(args.requirements).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith(("#", "--"))]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda line: audit(line, tags, args.python_version, args.extra_index_url), lines))
    report = {"platform": args.platform, "python": args.python_version, "checkedAt": datetime.now(timezone.utc).isoformat(), "scope": "Input requirements on PyPI and explicit indexes; tags/Requires-Python only, not runtime or native DLL validation", "packages": results}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for item in results:
        print(f"{item['status']:28} {item['name']} {item.get('version', '')}")
    return 1 if any(item["status"] == "metadata-error" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
