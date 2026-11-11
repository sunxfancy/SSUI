"""Install the verified Blender binary used by the real camera-solve CI test."""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


VERSION = "5.2.3"
BASE_URL = "https://download.blender.org/release/Blender5.2"
ARCHIVES = {
    ("linux", "x86_64"): (
        "blender-5.2.3-linux-x64.tar.xz",
        "78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec",
    ),
    ("darwin", "arm64"): (
        "blender-5.2.3-macos-arm64.dmg",
        "acc05374485a272342d4b323c15ac01953e7f697da2f1bad8af9c3bf087267a4",
    ),
    ("win32", "amd64"): (
        "blender-5.2.3-windows-x64.zip",
        "723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb",
    ),
}


def main() -> None:
    system = sys.platform
    machine = platform.machine().lower()
    filename, expected_hash = ARCHIVES[(system, machine)]
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    archive = temp / filename
    install = temp / f"ssui-blender-{VERSION}"
    install.mkdir(exist_ok=True)
    subprocess.run(
        ["curl", "--fail", "--location", "--retry", "3", "--output", str(archive),
         f"{BASE_URL}/{filename}"],
        check=True,
    )
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_hash:
        raise ValueError(f"Blender archive SHA-256 mismatch: {filename}")

    if system == "linux":
        with tarfile.open(archive, "r:xz") as bundle:
            bundle.extractall(install, filter="data")
        executable = install / f"blender-{VERSION}-linux-x64" / "blender"
    elif system == "win32":
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(install)
        executable = install / f"blender-{VERSION}-windows-x64" / "blender.exe"
    else:
        mount = temp / "ssui-blender-mount"
        mount.mkdir(exist_ok=True)
        subprocess.run(["hdiutil", "attach", str(archive), "-nobrowse", "-mountpoint", str(mount)], check=True)
        try:
            app = install / "Blender.app"
            shutil.copytree(mount / "Blender.app", app)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        executable = app / "Contents" / "MacOS" / "Blender"

    if not executable.is_file():
        raise FileNotFoundError(f"Blender executable missing after extraction: {executable}")
    subprocess.run([str(executable), "--background", "--factory-startup", "--python-expr",
                    f"import bpy; assert bpy.app.version_string.startswith('{VERSION}')"], check=True)
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as github_env:
        github_env.write(f"BLENDER_EXECUTABLE={executable}\n")
    print(f"Verified Blender {VERSION}: {executable}")


if __name__ == "__main__":
    main()
