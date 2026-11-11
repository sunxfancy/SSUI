import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import release


CARGO = """[package]
name = "ssui"
version = "0.1.1"

[dependencies]
serde = "1"
"""


class ParseTagTest(unittest.TestCase):
    def test_ok_bare(self):
        v = release.parse_tag("0.1.2")
        self.assertEqual(v.triple(), (0, 1, 2))
        self.assertEqual(v.dev, "")
        self.assertEqual(v.display(), "0.1.2")

    def test_ok_with_v_prefix(self):
        v = release.parse_tag("v0.1.2")
        self.assertEqual(v.triple(), (0, 1, 2))

    def test_rejects_prerelease_suffix(self):
        with self.assertRaises(ValueError):
            release.parse_tag("0.1.2-rc1")

    def test_rejects_non_version(self):
        with self.assertRaises(ValueError):
            release.parse_tag("latest")


class DowngradeTest(unittest.TestCase):
    def test_same_is_not_downgrade(self):
        a = release.parse_tag("0.1.2")
        self.assertFalse(release.is_downgrade(a, a))

    def test_newer_patch_ok(self):
        cur = release.parse_tag("0.1.1")
        incoming = release.parse_tag("0.1.2")
        self.assertFalse(release.is_downgrade(cur, incoming))

    def test_older_patch_is_downgrade(self):
        cur = release.parse_tag("0.1.2")
        incoming = release.parse_tag("0.1.1")
        self.assertTrue(release.is_downgrade(cur, incoming))


class CargoVersionTest(unittest.TestCase):
    def test_read(self):
        v = release.read_version(CARGO)
        self.assertEqual(v.display(), "0.1.1")

    def test_write_official_roundtrip(self):
        official = release.parse_tag("0.1.2")
        text = release.write_version(CARGO, official)
        self.assertEqual(release.read_version(text).display(), "0.1.2")

    def test_write_dev_roundtrip(self):
        text = release.write_version(CARGO, release.parse_tag("0.1.2").as_dev())
        self.assertEqual(release.read_version(text).display(), "0.1.2-dev")


class DocPathTest(unittest.TestCase):
    def test_whitelist(self):
        for p in (
            "Readme.md",
            "Readme.zh.md",
            "README.md",
            "Readme.en.md",
            "doc/usr/guide.md",
            "doc/BuildSystem.md",
        ):
            self.assertTrue(release.is_doc_path(p), p)

    def test_rejects_code(self):
        self.assertFalse(release.is_doc_path("package.json"))
        self.assertFalse(release.is_doc_path("desktop/src/App.tsx"))
        self.assertFalse(release.is_doc_path("docs-extra/foo.md"))


class MainPrAllowedTest(unittest.TestCase):
    def test_promote_head_allows_code_files(self):
        self.assertTrue(
            release.main_pr_allowed(
                "promote/v0.1.0", ["desktop/src/App.tsx", "desktop/src-tauri/Cargo.toml"]
            )
        )

    def test_docs_only_allowed(self):
        self.assertTrue(
            release.main_pr_allowed("docs/readme-fix", ["Readme.md", "doc/usr/README.md"])
        )

    def test_dev_code_pr_rejected(self):
        self.assertFalse(release.main_pr_allowed("dev", ["desktop/src/App.tsx"]))

    def test_isolation_branch_not_a_promote_head(self):
        self.assertFalse(release.main_pr_allowed("v0.1.0", ["desktop/src/App.tsx"]))

    def test_empty_non_promote_rejected(self):
        self.assertFalse(release.main_pr_allowed("hotfix", []))


class CheckMainPrTest(unittest.TestCase):
    def test_docs_pr_posts_success_check(self):
        r = release.FakeRunner()
        r.when(["git", "fetch", "origin", "main"], stdout="")
        r.when(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            stdout="Readme.md\n",
        )
        r.when(["git", "rev-parse", "HEAD"], stdout="abc123\n")
        r.when(["gh", "api"], stdout='{"id":1}\n')
        release.cmd_check_main_pr(r, head_ref="docs/readme-fix")
        api = " ".join(next(c for c in r.calls if c[:2] == ["gh", "api"]))
        self.assertIn("main-gate", api)
        self.assertIn("success", api)

    def test_code_pr_fails_and_posts_failure_check(self):
        r = release.FakeRunner()
        r.when(["git", "fetch", "origin", "main"], stdout="")
        r.when(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            stdout="desktop/src/App.tsx\n",
        )
        r.when(["git", "rev-parse", "HEAD"], stdout="abc123\n")
        r.when(["gh", "api"], stdout='{"id":1}\n')
        with self.assertRaises(SystemExit) as ctx:
            release.cmd_check_main_pr(r, head_ref="dev")
        self.assertNotEqual(ctx.exception.code, 0)
        api = " ".join(next(c for c in r.calls if c[:2] == ["gh", "api"]))
        self.assertIn("failure", api)


class RequireGhTest(unittest.TestCase):
    def test_missing_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            release.require_gh(which=lambda _: None)
        self.assertNotEqual(ctx.exception.code, 0)


class CheckVersionsTest(unittest.TestCase):
    def test_current_tree_is_consistent(self):
        release.cmd_check_versions(ROOT)

    def test_required_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "desktop/src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "desktop").mkdir(parents=True, exist_ok=True)
            (root / "desktop/src-tauri/Cargo.toml").write_text(
                '[package]\nname = "ssui"\nversion = "0.1.0"\n', encoding="utf-8"
            )
            (root / "desktop/package.json").write_text(
                '{"name": "ssui-desktop", "version": "9.9.9"}\n', encoding="utf-8"
            )
            with self.assertRaises(SystemExit):
                release.cmd_check_versions(root)

    def test_tracked_mismatch_only_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "desktop/src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "desktop").mkdir(parents=True, exist_ok=True)
            (root / "ssui-vscode").mkdir(parents=True, exist_ok=True)
            (root / "desktop/src-tauri/Cargo.toml").write_text(
                '[package]\nname = "ssui"\nversion = "0.1.0"\n', encoding="utf-8"
            )
            (root / "desktop/package.json").write_text(
                '{"name": "ssui-desktop", "version": "0.1.0"}\n', encoding="utf-8"
            )
            (root / "ssui-vscode/package.json").write_text(
                '{"name": "ssui-vscode", "version": "0.1.1"}\n', encoding="utf-8"
            )
            release.cmd_check_versions(root)


class CleanupBranchesTest(unittest.TestCase):
    def _runner(self):
        r = release.FakeRunner()
        r.when(["git", "fetch", "origin", "--prune"], stdout="")
        r.when(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short) %(objectname)",
                "refs/remotes/origin",
            ],
            stdout=(
                "origin/main mmm\n"
                "origin/dev ddd\n"
                "origin/v0.1.0 aaa\n"
                "origin/v0.2.0 bbb\n"
                "origin/promote/v0.1.0 ccc\n"
                "origin/rebase/v0.1.0 dd2\n"
                "origin/feature-x fff\n"
            ),
        )
        r.when(["git", "merge-base", "--is-ancestor", "aaa", "origin/dev"], rc=0)
        r.when(["git", "merge-base", "--is-ancestor", "bbb", "origin/dev"], rc=1)
        r.when(["git", "merge-base", "--is-ancestor", "ccc", "origin/main"], rc=0)
        r.when(["git", "merge-base", "--is-ancestor", "dd2", "origin/dev"], rc=0)
        r.when(["git", "push", "origin", "--delete"], stdout="")
        return r

    def test_deletes_merged_branches_only(self):
        r = self._runner()
        release.cmd_cleanup_branches(r)
        deletes = [c for c in r.calls if "--delete" in c]
        self.assertEqual(
            deletes,
            [
                ["git", "push", "origin", "--delete", "refs/heads/v0.1.0"],
                ["git", "push", "origin", "--delete", "refs/heads/promote/v0.1.0"],
                ["git", "push", "origin", "--delete", "refs/heads/rebase/v0.1.0"],
            ],
        )

    def test_dry_run_never_pushes(self):
        r = self._runner()
        release.cmd_cleanup_branches(r, dry_run=True)
        self.assertFalse(any(c[:2] == ["git", "push"] for c in r.calls))


class SyncDocsTest(unittest.TestCase):
    def _wire(self, r, diff_out):
        r.when(["git", "fetch", "origin", "main", "dev"], stdout="")
        r.when(
            ["git", "merge-base", "origin/main", "origin/dev"],
            stdout="base123\n",
        )
        r.when(["git", "diff", "--name-only", "base123", "origin/main"], stdout=diff_out)
        return r

    def test_rejects_non_doc_change(self):
        r = self._wire(release.FakeRunner(), "desktop/src/App.tsx\n")
        with self.assertRaises(SystemExit):
            release.cmd_sync_docs(r)
        self.assertFalse(any(c[:2] == ["git", "checkout"] for c in r.calls))

    def test_nothing_to_sync(self):
        r = self._wire(release.FakeRunner(), "")
        release.cmd_sync_docs(r)

    def test_syncs_docs_via_pr(self):
        r = self._wire(release.FakeRunner(), "Readme.md\ndoc/usr/guide.md\n")
        r.when(["git", "checkout", "-B", "sync-docs/from-main", "origin/dev"], stdout="")
        r.when(
            ["git", "checkout", "origin/main", "--", "Readme.md", "doc/usr/guide.md"],
            stdout="",
        )
        r.when(["git", "diff", "--cached", "--quiet"], rc=1)
        r.when(["git", "commit", "-m", "docs: sync documentation from main"], stdout="")
        r.when(
            ["git", "push", "-u", "origin", "sync-docs/from-main", "--force-with-lease"],
            stdout="",
        )
        r.when(
            ["gh", "pr", "list", "--base", "dev", "--head", "sync-docs/from-main"],
            stdout="[]\n",
        )
        r.when(["gh", "pr", "create"], stdout="https://example/pr/2\n")
        release.cmd_sync_docs(r)
        self.assertIn(
            ["git", "push", "-u", "origin", "sync-docs/from-main", "--force-with-lease"],
            r.calls,
        )
        self.assertTrue(any(c[:3] == ["gh", "pr", "create"] for c in r.calls))
        self.assertFalse(any(c == ["git", "push", "origin", "dev"] for c in r.calls))

    def test_dry_run_never_mutates(self):
        r = self._wire(release.FakeRunner(), "Readme.md\n")
        release.cmd_sync_docs(r, dry_run=True)
        self.assertFalse(any(c[:2] == ["git", "push"] for c in r.calls))
        self.assertFalse(any(c[:2] == ["git", "checkout"] for c in r.calls))

    def test_reuses_existing_pr(self):
        r = self._wire(release.FakeRunner(), "Readme.md\n")
        r.when(["git", "checkout", "-B", "sync-docs/from-main", "origin/dev"], stdout="")
        r.when(["git", "checkout", "origin/main", "--", "Readme.md"], stdout="")
        r.when(["git", "diff", "--cached", "--quiet"], rc=1)
        r.when(["git", "commit", "-m", "docs: sync documentation from main"], stdout="")
        r.when(
            ["git", "push", "-u", "origin", "sync-docs/from-main", "--force-with-lease"],
            stdout="",
        )
        r.when(
            ["gh", "pr", "list", "--base", "dev", "--head", "sync-docs/from-main"],
            stdout='[{"url":"https://example/pr/9"}]\n',
        )
        release.cmd_sync_docs(r)
        self.assertFalse(any(c[:3] == ["gh", "pr", "create"] for c in r.calls))


class StartTest(unittest.TestCase):
    def test_start_preserves_tag_and_rejects_unprepared_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pkg = root / "desktop/package.json"
            pkg.parent.mkdir(parents=True)
            pkg.write_text('{"version":"0.1.2"}')
            r = release.FakeRunner()
            r.cargo_text = release.write_version(CARGO, release.parse_tag("0.1.2"))
            r.when(["gh", "release", "view"], stdout='{"isPrerelease":true}')
            r.when(["git", "status"], stdout="")
            r.when(["git", "fetch"], stdout="")
            r.when(["git", "checkout"], stdout="")
            r.when(["git", "push"], stdout="")
            release.cmd_start(r, tag="0.1.2", repo_root=root, ci=True)
            self.assertFalse(any(c[:2] == ["git", "tag"] or "--force" in c for c in r.calls))
            r.cargo_text = CARGO
            with self.assertRaises(ValueError):
                release.cmd_start(r, tag="0.1.2", repo_root=root, ci=True)
            r.when(["gh", "release", "view"], stdout='{"isPrerelease":false}')
            with self.assertRaises(ValueError):
                release.cmd_start(r, tag="0.1.2", repo_root=root, ci=True)


class FinishTest(unittest.TestCase):
    def _base(self, *, on_main: bool = False):
        r = release.FakeRunner()
        r.cargo_text = release.write_version(CARGO, release.parse_tag("0.1.2"))
        r.when(["gh", "release", "edit", "0.1.2", "--prerelease=false"], stdout="")
        r.when(
            [
                "git",
                "fetch",
                "origin",
                "main",
                "dev",
                "refs/heads/v0.1.2",
                "refs/tags/0.1.2",
            ],
            stdout="",
        )
        r.when(["git", "rev-parse", "refs/tags/0.1.2^{commit}"], stdout="off123\n")
        r.when(
            ["git", "merge-base", "--is-ancestor", "off123", "origin/main"],
            rc=0 if on_main else 1,
        )
        r.when(["git", "branch", "-f", "promote/v0.1.2", "off123"], stdout="")
        r.when(["git", "push", "-u", "origin", "promote/v0.1.2"], stdout="")
        r.when(
            ["gh", "pr", "list", "--base", "main", "--head", "promote/v0.1.2"],
            stdout="[]\n",
        )
        r.when(["gh", "pr", "create"], stdout="https://example/pr/1\n")
        r.when(["gh", "api"], stdout='{"id":1}\n')
        r.when(
            ["git", "checkout", "-B", "v0.1.2", "refs/remotes/origin/v0.1.2"],
            stdout="",
        )
        r.when(["git", "checkout", "-B", "dev", "origin/dev"], stdout="")
        return r

    def _wire_rebase_ok(self, r, *, ahead="2"):
        r.when(["git", "rebase", "refs/heads/v0.1.2"], stdout="")
        r.when(["git", "rev-list", "--count", "origin/dev..HEAD"], stdout=f"{ahead}\n")
        r.when(["git", "checkout", "-B", "rebase/v0.1.2", "HEAD"], stdout="")
        r.when(
            ["git", "push", "-u", "origin", "rebase/v0.1.2", "--force-with-lease"],
            stdout="",
        )
        r.when(
            ["gh", "pr", "list", "--base", "dev", "--head", "rebase/v0.1.2"],
            stdout="[]\n",
        )

    def test_finish_opens_main_and_rebase_prs(self):
        r = self._base()
        self._wire_rebase_ok(r)
        release.cmd_finish(r, tag="0.1.2")
        self.assertNotIn(["gh", "release", "edit", "0.1.2", "--prerelease=false"], r.calls)
        self.assertFalse(any(c == ["git", "push", "origin", "main"] for c in r.calls))
        self.assertFalse(
            any(c == ["git", "push", "--force-with-lease", "origin", "dev"] for c in r.calls)
        )
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertEqual(len(prs), 2)
        main_pr = next(c for c in prs if "promote/v0.1.2" in c)
        rebase_pr = next(c for c in prs if "rebase/v0.1.2" in c)
        self.assertIn("--base", main_pr)
        self.assertIn("--head", rebase_pr)
        self.assertTrue(any(c[:2] == ["gh", "api"] for c in r.calls))

    def test_finish_skips_main_pr_when_already_on_main(self):
        r = self._base(on_main=True)
        self._wire_rebase_ok(r)
        release.cmd_finish(r, tag="0.1.2")
        self.assertFalse(any("promote/v0.1.2" in c for c in r.calls if c[:2] == ["git", "push"]))
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertTrue(all("promote/v0.1.2" not in c for c in prs))
        self.assertTrue(any("rebase/v0.1.2" in c for c in prs))

    def test_finish_skips_rebase_pr_when_dev_up_to_date(self):
        r = self._base()
        self._wire_rebase_ok(r, ahead="0")
        release.cmd_finish(r, tag="0.1.2")
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertEqual(len(prs), 1)
        self.assertIn("promote/v0.1.2", prs[0])
        self.assertFalse(any("rebase/v0.1.2" in c for c in prs))

    def test_finish_rebase_conflict_opens_pr(self):
        r = self._base()
        r.when(["git", "rebase", "refs/heads/v0.1.2"], rc=1)
        r.when(["git", "rebase", "--abort"], stdout="")
        r.when(["git", "checkout", "-B", "rebase/v0.1.2", "refs/heads/v0.1.2"], stdout="")
        r.when(
            ["git", "push", "-u", "origin", "rebase/v0.1.2", "--force-with-lease"],
            stdout="",
        )
        r.when(
            ["gh", "pr", "list", "--base", "dev", "--head", "rebase/v0.1.2"],
            stdout="[]\n",
        )
        release.cmd_finish(r, tag="0.1.2")
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertTrue(any("promote/v0.1.2" in c for c in prs))
        rebase_pr = next(c for c in prs if "rebase/v0.1.2" in c)
        self.assertIn("--base", rebase_pr)
        self.assertIn("dev", rebase_pr)

    def test_finish_reuses_existing_main_pr(self):
        r = self._base()
        r.when(
            ["gh", "pr", "list", "--base", "main", "--head", "promote/v0.1.2"],
            stdout='[{"url":"https://example/pr/9"}]\n',
        )
        self._wire_rebase_ok(r)
        release.cmd_finish(r, tag="0.1.2")
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertTrue(all("promote/v0.1.2" not in c for c in prs))
        self.assertTrue(any(c[:2] == ["gh", "api"] for c in r.calls))

    def test_finish_warns_when_actions_cannot_create_prs(self):
        r = self._base()
        self._wire_rebase_ok(r)
        r.when(
            ["gh", "pr", "create"],
            rc=1,
            stdout=(
                "pull request create failed: GraphQL: GitHub Actions is not "
                "permitted to create or approve pull requests (createPullRequest)"
            ),
        )
        # 不应抛出：正式发布已完成，PR 创建失败时降级为警告并给出手动命令
        release.cmd_finish(r, tag="0.1.2")
        prs = [c for c in r.calls if c[:3] == ["gh", "pr", "create"]]
        self.assertEqual(len(prs), 2)


class CliTest(unittest.TestCase):
    def test_check_main_pr_requires_gh(self):
        with self.assertRaises(SystemExit):
            release.main(["check-main-pr"], which=lambda _: None)

    def test_start_requires_gh(self):
        with self.assertRaises(SystemExit):
            release.main(["start", "--tag", "0.1.2"], which=lambda _: None)

    def test_finish_requires_gh(self):
        with self.assertRaises(SystemExit):
            release.main(["finish", "--tag", "0.1.2"], which=lambda _: None)


if __name__ == "__main__":
    unittest.main()
