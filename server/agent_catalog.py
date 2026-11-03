"""Source-owned extension SDK and example discovery without loading model code."""
import ast
from pathlib import Path

from fastapi import APIRouter, Query, Request
from server.agent_bridge import check_local

router = APIRouter(prefix="/api/agent", tags=["Agent project catalog"])


def project_catalog(root: Path):
    for manifest in sorted((root / "extensions").glob("*/ssextension.yaml")):
        extension = manifest.parent
        yield {"kind": "extension", "name": extension.name, "path": str(manifest),
               "manifest": manifest.read_text(encoding="utf-8")}
        for package in sorted(extension.glob("ssui_*")):
            for source in sorted(package.rglob("*.py")):
                module = ".".join(source.relative_to(extension).with_suffix("").parts)
                if module.endswith(".__init__"):
                    module = module[:-9]
                try:
                    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeError, SyntaxError) as exc:
                    yield {"kind": "error", "path": str(source), "error": str(exc)}
                    continue
                def describe(node, owner=""):
                    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                    return {"kind": "operator", "name": module + "." + owner + node.name,
                            "module": module, "callable": owner + node.name, "path": str(source),
                            "params": {arg.arg: ast.unparse(arg.annotation) if arg.annotation else "Any" for arg in args if arg.arg not in ("self", "cls")},
                            "returns": ast.unparse(node.returns) if node.returns else "Any",
                            "description": ast.get_docstring(node) or "",
                            "execution": "Use this SDK callable in a trusted SSUI script, then inspect/prepare/execute the script. Instance methods require constructing/loading their class first."}
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                        yield describe(node)
                    elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                        for method in node.body:
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and not method.name.startswith("_"):
                                yield describe(method, node.name + ".")
    for path in sorted((root / "examples").rglob("*")):
        if path.suffix.lower() in (".py", ".flow", ".canvas") and not any(part.startswith(".") or part in ("__pycache__", "vendor") for part in path.relative_to(root).parts):
            yield {"kind": "example", "name": path.relative_to(root).as_posix(), "path": str(path)}


@router.get("/catalog")
async def catalog(request: Request, search: str = "", kind: str = "", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    check_local(request)
    entries = [item for item in project_catalog(Path(__file__).resolve().parent.parent)
               if (not kind or item["kind"] == kind) and
               (not search or search.casefold() in str(item).casefold())]
    return {"items": entries[offset:offset + limit], "total": len(entries), "offset": offset,
            "next_offset": offset + limit if offset + limit < len(entries) else None,
            "availability": "Source discovery only; model weights and hardware availability are not guaranteed"}
