"""SSUI release / branch control helpers (ported from the EVEngine project).

Implements the quality gates the workflows rely on:

- check-versions: `desktop/src-tauri/Cargo.toml` is the version source of
  truth; "required" touchpoints must match it, "tracked" ones only warn.
- start: called on a GitHub pre-release; writes the official version, moves
  the tag to the release commit and pushes a vX.Y.Z release branch.
- check-main-pr: PRs into `main` must be documentation-only or come from a
  `promote/vMAJOR.MINOR.PATCH` release branch. Posts the `main-gate` check via
  the Checks API so GITHUB_TOKEN-created PRs stay mergeable.
- sync-docs: cherry-pick documentation changes from `main` onto `dev` through
  a PR (main is protected; dev never merges into main).
- cleanup-branches: delete merged release branches (vX.Y.Z / promote/vX.Y.Z /
  rebase/vX.Y.Z); release tags are never touched.
- finish: called after strict tests + packaging; marks the release formal and
  opens the promote/vX.Y.Z PR to `main` plus a rebase/vX.Y.Z PR to `dev`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PROMOTE_HEAD_RE = re.compile(r"^promote/v[0-9]+\.[0-9]+\.[0-9]+$")
TAG_RE = re.compile(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)$")
VERSION_BRANCH_RE = re.compile(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)$")
PROMOTE_BRANCH_RE = re.compile(r"^promote/v([0-9]+)\.([0-9]+)\.([0-9]+)$")
REBASE_BRANCH_RE = re.compile(r"^rebase/v([0-9]+)\.([0-9]+)\.([0-9]+)$")
DOC_FILES = frozenset({"Readme.md", "Readme.zh.md", "README.md", "Readme.en.md"})
# Non-doc files the release pipeline is allowed to rewrite on `main`. Empty
# until SSUI grows a scripted release flow; docs-only and promote/* PRs are
# the only paths through main-gate for now.
RELEASE_PATHS: frozenset[str] = frozenset()
DEV_BRANCH = "dev"
MAIN_BRANCH = "main"
MAIN_GATE_CHECK = "main-gate"

CARGO_MANIFEST = "desktop/src-tauri/Cargo.toml"
_CARGO_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_CARGO_VERSION_SET = re.compile(r'(^version\s*=\s*")([^"]*)(")', re.MULTILINE)
_JSON_VER_SET = re.compile(r'("version"\s*:\s*")([^"]*)(")')


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    dev: str = ""

    def triple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def display(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}{self.dev}"

    def official(self) -> Version:
        return Version(self.major, self.minor, self.patch, "")

    def as_dev(self) -> Version:
        return Version(self.major, self.minor, self.patch, "-dev")


def parse_tag(tag: str) -> Version:
    m = TAG_RE.fullmatch(tag)
    if not m:
        raise ValueError(f"tag must match [v]MAJOR.MINOR.PATCH, got {tag!r}")
    return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)), "")


def is_downgrade(current: Version, incoming: Version) -> bool:
    return incoming.triple() < current.triple()


def read_version(cargo_text: str) -> Version:
    m = _CARGO_VERSION.search(cargo_text)
    if not m:
        raise ValueError(f"{CARGO_MANIFEST} missing `version = \"...\"`")
    raw = m.group(1).strip()
    if raw.startswith(("v", "V")):
        raw = raw[1:]
    base, sep, dev = raw.partition("-")
    parts = base.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"{CARGO_MANIFEST}: cannot parse version {raw!r}")
    return Version(int(parts[0]), int(parts[1]), int(parts[2]), f"-{dev}" if sep else "")


def write_version(cargo_text: str, version: Version) -> str:
    new, n = _CARGO_VERSION_SET.subn(rf"\g<1>{version.display()}\g<3>", cargo_text, count=1)
    if n != 1:
        raise ValueError(f"{CARGO_MANIFEST} missing `version = \"...\"`")
    return new


@dataclass(frozen=True)
class VersionTouchpoint:
    """A file that carries the app version outside Cargo.toml.

    `kind` is either "required" (must match, enforced by check-versions) or
    "tracked" (independent packages; only reported as warnings).
    """

    path: str
    kind: str


VERSION_TOUCHPOINTS: tuple[VersionTouchpoint, ...] = (
    VersionTouchpoint("desktop/package.json", "required"),
    VersionTouchpoint("ssui-vscode/package.json", "tracked"),
    VersionTouchpoint("extension_builder/package.json", "tracked"),
    VersionTouchpoint("frontend/ssui_components/package.json", "tracked"),
    VersionTouchpoint("frontend/functional_ui/package.json", "tracked"),
    VersionTouchpoint("extensions/Image/package.json", "tracked"),
    VersionTouchpoint("extensions/example/package.json", "tracked"),
)


def read_cargo_version(text: str) -> str:
    m = _CARGO_VERSION.search(text)
    if not m:
        raise ValueError(f'{CARGO_MANIFEST} missing `version = "..."`')
    return m.group(1).strip()


def _read_json_version(root: Path, rel: str) -> str | None:
    path = root / rel
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{rel}: invalid JSON: {exc}") from exc
    version = data.get("version")
    return str(version) if version is not None else None


def cmd_check_versions(root: Path) -> None:
    """Validate that every version touchpoint matches the desktop crate."""
    manifest = root / CARGO_MANIFEST
    if not manifest.exists():
        print(f"error: required version file missing: {CARGO_MANIFEST}", file=sys.stderr)
        raise SystemExit(1)
    version = read_cargo_version(manifest.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    for tp in VERSION_TOUCHPOINTS:
        current = _read_json_version(root, tp.path)
        if current is None:
            msg = f"{tp.path}: file missing or no `version` field"
        elif current != version:
            msg = f"{tp.path}: {current!r} != expected {version!r}"
        else:
            continue
        if tp.kind == "required":
            errors.append(msg)
        else:
            warnings.append(msg)
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            f"error: desktop crate version {version} is not consistent across required "
            "touchpoints",
            file=sys.stderr,
        )
        raise SystemExit(1)
    required = sum(1 for tp in VERSION_TOUCHPOINTS if tp.kind == "required")
    print(f"OK: {required} required version touchpoints match {version}")


def sync_version_files(root: Path, version: Version, *, dry_run: bool = False) -> list[str]:
    """Rewrite required version touchpoints under `root` to `version`.

    Cargo.toml is handled separately by `cmd_start`; this covers the other
    required touchpoints (desktop/package.json) and returns the repo-relative
    paths that actually changed. Missing required files are a hard error.
    """
    changed: list[str] = []
    for tp in VERSION_TOUCHPOINTS:
        if tp.kind != "required":
            continue
        path = root / tp.path
        if not path.exists():
            print(f"error: required version file missing: {tp.path}", file=sys.stderr)
            raise SystemExit(1)
        text = path.read_text(encoding="utf-8")
        new_text = _JSON_VER_SET.sub(rf"\g<1>{version.display()}\g<3>", text, count=1)
        if new_text != text:
            if dry_run:
                print(f"+ update {tp.path} -> {version.display()}")
            else:
                path.write_text(new_text, encoding="utf-8")
            changed.append(tp.path)
    return changed


def _load_cargo(runner: Runner, cargo_path: Path) -> str:
    if isinstance(runner, FakeRunner):
        return runner.cargo_text
    return cargo_path.read_text(encoding="utf-8")


def _store_cargo(runner: Runner, cargo_path: Path, text: str, *, dry_run: bool) -> None:
    if isinstance(runner, FakeRunner):
        runner.cargo_text = text
    elif not dry_run:
        cargo_path.write_text(text, encoding="utf-8")


def _write_github_output(tag: str, branch: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"tag={tag}\nbranch={branch}\n")


def _latest_prerelease_tag(runner: Runner) -> str:
    raw = runner.run(["gh", "release", "list", "--json", "tagName,isPrerelease", "--limit", "20"])
    items = json.loads(raw) if raw.strip() else []
    for item in items:
        if item.get("isPrerelease"):
            return str(item["tagName"])
    print("error: no open pre-release found; pass --tag", file=sys.stderr)
    raise SystemExit(1)


def is_doc_path(path: str) -> bool:
    norm = path.replace("\\", "/").lstrip("./")
    if norm in DOC_FILES:
        return True
    return norm == "doc" or norm.startswith("doc/")


def is_release_path(path: str) -> bool:
    return path.replace("\\", "/").lstrip("./") in RELEASE_PATHS


def is_promote_head(head_ref: str) -> bool:
    ref = head_ref.replace("\\", "/")
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        ref = ref[len(prefix):]
    return bool(PROMOTE_HEAD_RE.fullmatch(ref))


def main_pr_allowed(head_ref: str, changed_files: list[str]) -> bool:
    if is_promote_head(head_ref):
        return True
    if not changed_files:
        return False
    return all(is_doc_path(p) for p in changed_files)


class CommandError(RuntimeError):
    def __init__(self, argv: list[str], returncode: int, stderr: str):
        super().__init__(f"command failed ({returncode}): {' '.join(argv)}\n{stderr}")
        self.argv = argv
        self.returncode = returncode
        self.stderr = stderr


class Runner:
    def run(self, argv: list[str], *, check: bool = True) -> str:
        raise NotImplementedError


class RealRunner(Runner):
    def __init__(self, *, dry_run: bool = False, cwd: Path | None = None):
        self.dry_run = dry_run
        self.cwd = cwd

    def run(self, argv: list[str], *, check: bool = True) -> str:
        if self.dry_run:
            print("+", " ".join(argv))
            return ""
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=self.cwd)
        if check and proc.returncode != 0:
            raise CommandError(argv, proc.returncode, proc.stderr)
        return proc.stdout


class FakeRunner(Runner):
    """Match commands by argv prefix; used by the unit tests."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self._rules: list[tuple[list[str], str, int]] = []
        self.cargo_text: str = ""

    def when(self, prefix: list[str], *, stdout: str = "", rc: int = 0) -> None:
        self._rules.append((prefix, stdout, rc))

    def run(self, argv: list[str], *, check: bool = True) -> str:
        self.calls.append(list(argv))
        for prefix, stdout, rc in reversed(self._rules):
            if argv[: len(prefix)] == prefix:
                if rc != 0 and check:
                    raise CommandError(argv, rc, stdout)
                return stdout
        raise AssertionError(f"unexpected command: {argv}")


def require_gh(which: Callable[[str], str | None] | None = None) -> None:
    lookup = which or shutil.which
    if lookup("gh"):
        return
    print(
        "error: GitHub CLI (gh) not found on PATH. Install from https://cli.github.com/",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _is_ancestor(runner: Runner, commit: str, ref: str) -> bool:
    try:
        runner.run(["git", "merge-base", "--is-ancestor", commit, ref])
        return True
    except CommandError:
        return False


def _existing_pr_url(runner: Runner, *, base: str, head: str) -> str:
    raw = runner.run(
        [
            "gh",
            "pr",
            "list",
            "--base",
            base,
            "--head",
            head,
            "--state",
            "open",
            "--json",
            "url",
        ]
    )
    if not raw.strip():
        return ""
    items = json.loads(raw)
    if not items:
        return ""
    return str(items[0].get("url") or "")


def _ensure_pr(
    runner: Runner,
    *,
    base: str,
    head: str,
    title: str,
    body: str,
) -> str:
    existing = _existing_pr_url(runner, base=base, head=head)
    if existing:
        print(f"PR already open: {existing}")
        return existing
    return runner.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            head,
            "--title",
            title,
            "--body",
            body,
        ]
    ).strip()


def _is_pr_permission_error(exc: CommandError) -> bool:
    """True when gh cannot create PRs because GitHub Actions lacks the
    'Allow GitHub Actions to create and approve pull requests' permission."""
    return "not permitted to create or approve pull requests" in (exc.stderr or "").lower()


def _open_pr_or_warn(
    runner: Runner,
    *,
    base: str,
    head: str,
    title: str,
    body: str,
) -> None:
    """Open a PR, or warn with manual steps when Actions may not create PRs.

    The repository setting "Allow GitHub Actions to create and approve pull
    requests" is UI-only and cannot be enabled from a workflow. When it is
    disabled, finish should still complete (the release is already formal and
    assets uploaded) and tell the maintainer exactly what to open manually.
    """
    try:
        _ensure_pr(runner, base=base, head=head, title=title, body=body)
    except CommandError as exc:
        if not _is_pr_permission_error(exc):
            raise
        print(
            "warning: GitHub Actions is not permitted to create pull requests; "
            f"open it manually with:\n"
            f"  gh pr create --base {base} --head {head} --title {title!r}",
            file=sys.stderr,
        )


def post_check(
    runner: Runner,
    *,
    sha: str,
    conclusion: str,
    title: str,
    summary: str,
    name: str = MAIN_GATE_CHECK,
) -> None:
    if not sha:
        return
    runner.run(
        [
            "gh",
            "api",
            "--method",
            "POST",
            "repos/{owner}/{repo}/check-runs",
            "-f",
            f"name={name}",
            "-f",
            f"head_sha={sha}",
            "-f",
            "status=completed",
            "-f",
            f"conclusion={conclusion}",
            "-f",
            f"output[title]={title}",
            "-f",
            f"output[summary]={summary}",
        ]
    )


def cmd_start(
    runner: Runner,
    *,
    tag: str,
    repo_root: Path,
    ci: bool,
    dry_run: bool = False,
) -> None:
    """Turn a GitHub pre-release into an official release branch + commit.

    Called from the Release workflow on `release: prereleased`. The tag is
    expected to be `[v]MAJOR.MINOR.PATCH`. Writes the official version into
    Cargo.toml and the required touchpoints, moves the tag to the release
    commit and pushes a vX.Y.Z branch that CI then builds and packages.
    """
    incoming = parse_tag(tag)
    branch = f"v{incoming.display()}"
    view = runner.run(["gh", "release", "view", tag, "--json", "tagName,isPrerelease"])
    meta = json.loads(view) if view.strip() else {"tagName": tag, "isPrerelease": True}
    is_pre = bool(meta.get("isPrerelease"))

    dirty = runner.run(["git", "status", "--porcelain"], check=False)
    if not ci and dirty.strip():
        print("error: working tree is dirty; commit or stash first", file=sys.stderr)
        raise SystemExit(1)

    runner.run(["git", "fetch", "origin", "tag", tag, "--force"])
    # The release branch and the release tag share a similar short name
    # (refs/heads/vX.Y.Z vs refs/tags/0.1.2). Always use explicit refspecs so
    # git never sees an ambiguous `git push origin vX.Y.Z`.
    runner.run(["git", "checkout", "-B", branch, f"refs/tags/{tag}"])

    text = _load_cargo(runner, repo_root / CARGO_MANIFEST)
    current = read_version(text)
    if is_downgrade(current, incoming):
        print(
            f"error: refusing to downgrade {current.display()} to {incoming.display()}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    already_official = current.triple() == incoming.triple() and current.dev == ""
    if not is_pre and not already_official:
        print(
            "error: release is already formal but the tree is not the official version; "
            "will not rewrite a published tag",
            file=sys.stderr,
        )
        raise SystemExit(1)

    new_text = write_version(text, incoming.official())
    _store_cargo(runner, repo_root / CARGO_MANIFEST, new_text, dry_run=dry_run)
    touched = [CARGO_MANIFEST]
    touched += sync_version_files(repo_root, incoming.official(), dry_run=dry_run)
    runner.run(["git", "add", *touched])
    try:
        runner.run(["git", "diff", "--cached", "--quiet"])
    except CommandError:
        runner.run(["git", "commit", "-m", f"release: {incoming.display()}"])
    runner.run(["git", "tag", "-f", tag])
    runner.run(["git", "push", "-u", "origin", f"refs/heads/{branch}"])
    runner.run(["git", "push", "--force", "origin", f"refs/tags/{tag}"])
    _write_github_output(tag, branch)


def _open_promote_pr(runner: Runner, *, branch: str, official: str) -> None:
    promote = f"promote/{branch}"
    if _is_ancestor(runner, official, f"origin/{MAIN_BRANCH}"):
        print(f"{MAIN_BRANCH} already contains {branch}")
        return
    runner.run(["git", "branch", "-f", promote, official])
    runner.run(["git", "push", "-u", "origin", promote, "--force-with-lease"])
    body = (
        f"Promote `{branch}` to `{MAIN_BRANCH}`.\n\n"
        f"This PR points at the official release commit. "
        f"Merge it to update the default branch. Do not merge `{DEV_BRANCH}` into `{MAIN_BRANCH}`.\n"
    )
    _open_pr_or_warn(
        runner,
        base=MAIN_BRANCH,
        head=promote,
        title=f"release: {branch}",
        body=body,
    )
    post_check(
        runner,
        sha=official,
        conclusion="success",
        title="release promote",
        summary=f"{promote} is allowed onto {MAIN_BRANCH}.",
    )


def _open_rebase_pr(runner: Runner, *, branch: str, conflict: bool) -> None:
    head = f"rebase/{branch}"
    if conflict:
        body = (
            f"Automatic rebase of `{DEV_BRANCH}` onto `{branch}` failed.\n\n"
            f"Resolve on this branch or locally:\n\n"
            f"```\n"
            f"git fetch origin\n"
            f"git checkout {DEV_BRANCH}\n"
            f"git rebase {branch}\n"
            f"# fix conflicts, then push this rebase branch (do not force-push {DEV_BRANCH} unless you intend to):\n"
            f"git push --force-with-lease origin {head}\n"
            f"```\n"
        )
    else:
        body = (
            f"Automatic rebase of `{DEV_BRANCH}` onto `{branch}` succeeded.\n\n"
            f"Merge this PR to update `{DEV_BRANCH}`. Do not merge `{DEV_BRANCH}` into `{MAIN_BRANCH}`.\n"
        )
    _open_pr_or_warn(
        runner,
        base=DEV_BRANCH,
        head=head,
        title=f"rebase {DEV_BRANCH} onto {branch}",
        body=body,
    )


def cmd_finish(
    runner: Runner,
    *,
    tag: str,
    dry_run: bool = False,
) -> None:
    """Mark the release formal and open promote/rebase PRs.

    Called by the Release workflow after strict tests, packaging and the
    executable smoke test have all passed. `gh release edit --prerelease=false`
    is the actual "formal publish" step; promote/vX.Y.Z passes main-gate, and
    rebase/vX.Y.Z carries the release back onto `dev`.
    """
    incoming = parse_tag(tag)
    branch = f"v{incoming.display()}"
    runner.run(["gh", "release", "edit", tag, "--prerelease=false"])
    runner.run(
        [
            "git",
            "fetch",
            "origin",
            MAIN_BRANCH,
            DEV_BRANCH,
            f"refs/heads/{branch}",
            f"refs/tags/{tag}",
        ]
    )
    official = runner.run(["git", "rev-parse", f"refs/tags/{tag}"]).strip()
    _open_promote_pr(runner, branch=branch, official=official)

    # Ensure the local release branch exists (CI built it, we did not push it),
    # then rebase dev onto it. SSUI keeps plain MAJOR.MINOR.PATCH versions, so
    # there is no -dev write-back commit here.
    runner.run(["git", "checkout", "-B", branch, f"refs/remotes/origin/{branch}"])
    runner.run(["git", "checkout", "-B", DEV_BRANCH, f"origin/{DEV_BRANCH}"])
    rebase_head = f"rebase/{branch}"
    try:
        runner.run(["git", "rebase", f"refs/heads/{branch}"])
    except CommandError:
        runner.run(["git", "rebase", "--abort"])
        runner.run(["git", "checkout", "-B", rebase_head, f"refs/heads/{branch}"])
        runner.run(["git", "push", "-u", "origin", rebase_head, "--force-with-lease"])
        _open_rebase_pr(runner, branch=branch, conflict=True)
        return

    ahead_raw = runner.run(["git", "rev-list", "--count", f"origin/{DEV_BRANCH}..HEAD"]).strip()
    ahead = int(ahead_raw or "0")
    if ahead == 0:
        print(f"{DEV_BRANCH} already contains the rebased history")
        return
    runner.run(["git", "checkout", "-B", rebase_head, "HEAD"])
    runner.run(["git", "push", "-u", "origin", rebase_head, "--force-with-lease"])
    _open_rebase_pr(runner, branch=branch, conflict=False)


def cmd_check_main_pr(runner: Runner, *, head_ref: str | None = None) -> None:
    head = head_ref or os.environ.get("GITHUB_HEAD_REF") or ""
    runner.run(["git", "fetch", "origin", MAIN_BRANCH], check=False)
    names = runner.run(["git", "diff", "--name-only", f"origin/{MAIN_BRANCH}...HEAD"])
    files = [line.strip() for line in names.splitlines() if line.strip()]
    sha = runner.run(["git", "rev-parse", "HEAD"]).strip()
    allowed = main_pr_allowed(head, files)
    post_check(
        runner,
        sha=sha,
        conclusion="success" if allowed else "failure",
        title="main gate",
        summary=(
            f"{head} is allowed onto {MAIN_BRANCH}."
            if allowed
            else f"{head} is not a docs-only or promote/vX.X.X PR."
        ),
    )
    if allowed:
        return
    print(
        f"error: PRs to {MAIN_BRANCH} must be documentation-only "
        f"or come from a `promote/vMAJOR.MINOR.PATCH` release branch. Got {head!r}: "
        + ", ".join(files),
        file=sys.stderr,
    )
    raise SystemExit(1)


def cmd_cleanup_branches(runner: Runner, *, dry_run: bool = False) -> None:
    """Delete release branches once their PRs have been merged.

    - vX.Y.Z: deleted when its -dev write-back reached `dev` (rebase PR merged)
    - promote/vX.Y.Z: deleted when its official commit reached `main`
    - rebase/vX.Y.Z: deleted when its tip reached `dev`

    The tag refs/tags/vX.Y.Z is never touched. `main` / `dev` are never
    deleted.
    """
    runner.run(["git", "fetch", "origin", "--prune"])
    refs = runner.run(
        ["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/remotes/origin"]
    )
    deleted: list[str] = []
    for line in refs.splitlines():
        if not line.strip():
            continue
        short, sha = line.split(" ", 1)
        if not short.startswith("origin/"):
            continue
        name = short[len("origin/"):]
        if VERSION_BRANCH_RE.fullmatch(name):
            target = DEV_BRANCH
        elif PROMOTE_BRANCH_RE.fullmatch(name):
            target = MAIN_BRANCH
        elif REBASE_BRANCH_RE.fullmatch(name):
            target = DEV_BRANCH
        else:
            continue
        if not _is_ancestor(runner, sha, f"origin/{target}"):
            print(f"keep {name}: not merged into {target}")
            continue
        if dry_run:
            print(f"+ delete {name} (merged into {target})")
            continue
        runner.run(["git", "push", "origin", "--delete", f"refs/heads/{name}"])
        deleted.append(name)
        print(f"deleted {name} (merged into {target})")
    if not deleted and not dry_run:
        print("no release branches to clean up")


def cmd_sync_docs(runner: Runner, *, dry_run: bool = False) -> None:
    """Sync documentation-only changes from `main` onto `dev`.

    - Only paths that changed on `main` since the merge-base with `dev` are
      considered, so `dev`-only work is never touched.
    - Non-doc changes on `main` are rejected unless they are release-version
      touchpoints (RELEASE_PATHS); those reach `dev` through the release
      pipeline's rebase PR, and treating them as errors would make every
      sync-docs run after a release fail spuriously.
    - The sync is PR-based (`sync-docs/from-main` -> `dev`), matching the
      "no direct push to dev" model. Doc content is copied from `main`, so
      merge / squash / rebase merges on `main` are all handled.
    """
    runner.run(["git", "fetch", "origin", MAIN_BRANCH, DEV_BRANCH])
    base = runner.run(
        ["git", "merge-base", f"origin/{MAIN_BRANCH}", f"origin/{DEV_BRANCH}"]
    ).strip()
    changed = runner.run(["git", "diff", "--name-only", base, f"origin/{MAIN_BRANCH}"])
    files = [line.strip() for line in changed.splitlines() if line.strip()]
    bad = [f for f in files if not is_doc_path(f) and not is_release_path(f)]
    if bad:
        print(
            f"error: {MAIN_BRANCH} is ahead of {DEV_BRANCH} with non-doc files: "
            + ", ".join(bad)
            + f". Land those changes on {DEV_BRANCH} instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    doc_paths = [f for f in files if is_doc_path(f)]
    if not doc_paths:
        print("nothing to sync")
        return
    print(f"syncing {len(doc_paths)} documentation path(s) from {MAIN_BRANCH}:")
    for path in doc_paths:
        print(f"  {path}")
    if dry_run:
        return
    runner.run(["git", "checkout", "-B", "sync-docs/from-main", f"origin/{DEV_BRANCH}"])
    runner.run(["git", "checkout", f"origin/{MAIN_BRANCH}", "--", *doc_paths])
    try:
        runner.run(["git", "diff", "--cached", "--quiet"])
    except CommandError:
        runner.run(["git", "commit", "-m", f"docs: sync documentation from {MAIN_BRANCH}"])
    else:
        print("nothing to sync (docs already in sync)")
        return
    runner.run(["git", "push", "-u", "origin", "sync-docs/from-main", "--force-with-lease"])
    body = (
        f"Sync documentation changes from `{MAIN_BRANCH}` onto `{DEV_BRANCH}`.\n\n"
        f"Merge this PR to keep `{DEV_BRANCH}` docs in sync. "
        f"Do not merge `{DEV_BRANCH}` into `{MAIN_BRANCH}`.\n"
    )
    _ensure_pr(
        runner,
        base=DEV_BRANCH,
        head="sync-docs/from-main",
        title=f"docs: sync from {MAIN_BRANCH}",
        body=body,
    )


def main(
    argv: list[str] | None = None,
    *,
    which: Callable[[str], str | None] | None = None,
    runner: Runner | None = None,
) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SSUI release / branch control helper")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(required=True)
    sub.dest = "cmd"
    p_start = sub.add_parser("start")
    p_start.add_argument("--tag")
    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--tag", required=True)
    sub.add_parser("sync-docs")
    sub.add_parser("check-main-pr")
    sub.add_parser("check-versions")
    sub.add_parser("cleanup-branches")
    args = parser.parse_args(argv)

    real = runner or RealRunner(dry_run=args.dry_run)
    root = Path(__file__).resolve().parent.parent
    ci = os.environ.get("CI", "").lower() in {"1", "true", "yes"}

    if args.cmd == "start":
        require_gh(which=which)
        tag = args.tag or _latest_prerelease_tag(real)
        cmd_start(real, tag=tag, repo_root=root, ci=ci, dry_run=args.dry_run)
    elif args.cmd == "finish":
        require_gh(which=which)
        cmd_finish(real, tag=args.tag, dry_run=args.dry_run)
    elif args.cmd == "check-main-pr":
        require_gh(which=which)
        cmd_check_main_pr(real)
    elif args.cmd == "check-versions":
        cmd_check_versions(root)
    elif args.cmd == "sync-docs":
        require_gh(which=which)
        cmd_sync_docs(real, dry_run=args.dry_run)
    elif args.cmd == "cleanup-branches":
        cmd_cleanup_branches(real, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
