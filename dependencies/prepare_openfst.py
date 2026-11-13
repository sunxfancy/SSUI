"""Build the pinned OpenFst GRM SDK needed by Pynini on Linux ARM64."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlparse

VERSION = "1.8.4"
# MacPorts' public distfile is byte-identical to the upstream release. Keep
# the original SHA-256; upstream's download endpoint currently returns 403.
SOURCE_URL = f"https://distfiles-origin.macports.org/openfst/openfst-{VERSION}.tar.gz"
SOURCE_SHA256 = "a8ebbb6f3d92d07e671500587472518cfc87cb79b9a654a5a8abb2d0eb298016"
CONFIGURE = ["--enable-grm", "--enable-shared", "--disable-static", "--disable-bin"]
REQUIRED = ["include/fst/util.h", "include/fst/extensions/far/far.h",
            "lib/libfst.so", "lib/libfstscript.so", "lib/libfstfar.so",
            "lib/libfstfarscript.so", "lib/libfstpdtscript.so", "lib/libfstmpdtscript.so"]


def verify_archive(archive):
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(f"OpenFst {VERSION} source SHA-256 mismatch: {digest}")


def fetch_archive(url, dest):
    if urlparse(url).scheme != "https":
        raise ValueError("OpenFst source must use HTTPS")
    # No insecure TLS context, alternate origin, proxy or retry on refusal.
    class HttpsRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlparse(newurl).scheme != "https":
                raise RuntimeError("Refusing a non-HTTPS source redirect")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = urllib.request.build_opener(HttpsRedirect())
    with opener.open(url, timeout=120) as response:
        if urlparse(response.geturl()).scheme != "https":
            raise RuntimeError("Refusing a non-HTTPS source redirect")
        with Path(dest).open("wb") as output:
            shutil.copyfileobj(response, output)
    verify_archive(dest)


def build(prefix, archive=None, source_url=SOURCE_URL, jobs=2):
    prefix = Path(prefix).resolve()
    recipe = dict(version=VERSION, sha256=SOURCE_SHA256, configure=CONFIGURE,
                  machine=platform.machine(), cxxflags="-O2 -g0 -std=c++17")
    stamp = prefix / "ssui-recipe.json"
    if (stamp.is_file() and json.loads(stamp.read_text()) == recipe
            and all((prefix / name).is_file() for name in REQUIRED)):
        return
    for command in ("c++", "make"):
        if not shutil.which(command):
            raise RuntimeError(f"OpenFst requires {command}; install the native C++ build tools")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openfst-build-", dir=prefix.parent) as work:
        work = Path(work)
        source_archive = Path(archive).resolve() if archive else work / "source.tar.gz"
        if archive:
            verify_archive(source_archive)
        else:
            fetch_archive(source_url, source_archive)
        with tarfile.open(source_archive) as source:
            source.extractall(work, filter="data")
        source_dir = work / f"openfst-{VERSION}"
        env = dict(os.environ)
        env["CXXFLAGS"] = recipe["cxxflags"]
        for args in (["./configure", f"--prefix={prefix}", *CONFIGURE],
                     ["make", f"-j{jobs}"], ["make", "install"]):
            subprocess.run(args, cwd=source_dir, env=env, check=True,
                           stdout=sys.stderr, stderr=sys.stderr)
    missing = [name for name in REQUIRED if not (prefix / name).is_file()]
    if missing:
        raise RuntimeError(f"OpenFst GRM SDK incomplete: {missing}")
    stamp.write_text(json.dumps(recipe, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prefix", type=Path, required=True)
    p.add_argument("--archive", type=Path, default=os.environ.get("SSUI_OPENFST_ARCHIVE"))
    p.add_argument("--jobs", type=int, default=2)
    args = p.parse_args()
    if sys.platform != "linux" or platform.machine() not in ("aarch64", "arm64"):
        p.error("This source prerequisite is for Linux ARM64; other targets retain their native packages")
    if args.jobs < 1:
        p.error("--jobs must be positive")
    build(args.prefix, args.archive, jobs=args.jobs)
    prefix = args.prefix.resolve()
    def prepend(name, value, separator):
        return value + (separator + os.environ[name] if os.environ.get(name) else "")
    print(json.dumps({
        "CPLUS_INCLUDE_PATH": prepend("CPLUS_INCLUDE_PATH", str(prefix / "include"), ":"),
        "LIBRARY_PATH": prepend("LIBRARY_PATH", str(prefix / "lib"), ":"),
        "LD_LIBRARY_PATH": prepend("LD_LIBRARY_PATH", str(prefix / "lib"), ":"),
        "LDFLAGS": prepend("LDFLAGS", f"-L{prefix / 'lib'} -Wl,-rpath,{prefix / 'lib'}", " "),
    }))


if __name__ == "__main__":
    main()
