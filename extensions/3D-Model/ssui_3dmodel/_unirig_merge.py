"""Execute UniRig's GLB merge without its unused Open3D visualization import."""
import ast
from pathlib import Path
import sys


if __name__ == "__main__":
    sys.path.insert(0, str(Path.cwd()))
    source = Path.cwd() / "src/inference/merge.py"
    text = source.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source))
    # Keep the reference merge implementation intact. Open3D is not referenced
    # by it; do not mask missing functionality if a later upstream starts using it.
    if any(isinstance(node, ast.Name) and node.id == "o3d" for node in ast.walk(tree)):
        raise RuntimeError("This UniRig merge revision uses Open3D; install Open3D before running it")
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Import) and any(alias.name == "open3d" for alias in node.names))]
    exec(compile(tree, str(source), "exec"), {
        "__name__": "__main__", "__file__": str(source), "__package__": "src.inference"})
