"""Compile SSUI ``.flow`` graphs into ordinary executable Python scripts.

The flow file is deliberately a small, versioned JSON document.  Keeping the
compiler on the Python side means every caller (desktop UI, HTTP API and the
executor) observes exactly the same graph semantics.
"""

from __future__ import annotations

import ast
import hashlib
import json
import keyword
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FlowCompileError(ValueError):
    """A user-facing validation error in a flow document."""


@dataclass(frozen=True)
class Endpoint:
    node: str
    port: str


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
        raise FlowCompileError(f"{context} must be a valid Python identifier")
    return value


def _dotted_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise FlowCompileError(f"{context} must be a dotted Python name")
    for part in value.split("."):
        _identifier(part, context)
    return value


def _type_expression(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FlowCompileError(f"{context} must be a Python type expression")
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError as exc:
        raise FlowCompileError(f"{context} is not a valid Python type expression") from exc

    allowed = (
        ast.Expression,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Tuple,
        ast.List,
        ast.Load,
        ast.Constant,
        ast.BinOp,
        ast.BitOr,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise FlowCompileError(f"{context} contains unsupported syntax")
    return value.strip()


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise FlowCompileError(f"{context} must be a list")
    return value


def _ports(items: Any, context: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for index, item in enumerate(_list(items, context)):
        if not isinstance(item, dict):
            raise FlowCompileError(f"{context}[{index}] must be an object")
        port_id = _identifier(item.get("id"), f"{context}[{index}].id")
        name = _identifier(item.get("name"), f"{context}[{index}].name")
        type_name = _type_expression(item.get("type"), f"{context}[{index}].type")
        if port_id in seen_ids or name in seen_names:
            raise FlowCompileError(f"{context} contains a duplicate id or name")
        seen_ids.add(port_id)
        seen_names.add(name)
        result.append({"id": port_id, "name": name, "type": type_name})
    return result


def _endpoint(value: Any, context: str) -> Endpoint:
    if not isinstance(value, dict):
        raise FlowCompileError(f"{context} must be an object")
    node = value.get("node")
    if node not in ("$input", "$output"):
        node = _identifier(node, f"{context}.node")
    return Endpoint(node=node, port=_identifier(value.get("port"), f"{context}.port"))


def _literal(value: Any, context: str) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_literal(v, context) for v in value) + "]"
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return "{" + ", ".join(f"{k!r}: {_literal(v, context)}" for k, v in value.items()) + "}"
    raise FlowCompileError(f"{context} must contain JSON literal values")


def compile_flow_data(data: Any, source_name: str = "<flow>") -> str:
    """Validate *data* and return deterministic Python source code."""
    if not isinstance(data, dict):
        raise FlowCompileError("flow root must be an object")
    if data.get("version") != 1:
        raise FlowCompileError("unsupported flow version; expected 1")

    imports = _list(data.get("imports", []), "imports")
    import_lines: list[str] = []
    for index, item in enumerate(imports):
        if not isinstance(item, dict):
            raise FlowCompileError(f"imports[{index}] must be an object")
        module = _dotted_name(item.get("module"), f"imports[{index}].module")
        names = [_identifier(v, f"imports[{index}].names") for v in _list(item.get("names"), f"imports[{index}].names")]
        if not names:
            raise FlowCompileError(f"imports[{index}].names must not be empty")
        import_lines.append(f"from {module} import {', '.join(names)}")

    raw_functions = _list(data.get("functions"), "functions")
    if not raw_functions:
        raise FlowCompileError("functions must not be empty")

    functions: dict[str, dict[str, Any]] = {}
    function_names: set[str] = set()
    for index, raw in enumerate(raw_functions):
        context = f"functions[{index}]"
        if not isinstance(raw, dict):
            raise FlowCompileError(f"{context} must be an object")
        function_id = _identifier(raw.get("id"), f"{context}.id")
        name = _identifier(raw.get("name"), f"{context}.name")
        if function_id in functions or name in function_names:
            raise FlowCompileError("function ids and names must be unique")
        function_names.add(name)
        functions[function_id] = {
            **raw,
            "id": function_id,
            "name": name,
            "inputs": _ports(raw.get("inputs", []), f"{context}.inputs"),
            "outputs": _ports(raw.get("outputs", []), f"{context}.outputs"),
        }

    lines = [
        f"# Generated from {Path(source_name).name}; do not edit by hand.",
        "from typing import Tuple",
        "from ssui import SSUIConfig, workflow",
        *import_lines,
        "",
        "config = SSUIConfig()",
    ]
    for function in functions.values():
        lines.extend(["", *_compile_function(function, functions)])
    return "\n".join(lines) + "\n"


def _compile_function(function: dict[str, Any], functions: dict[str, dict[str, Any]]) -> list[str]:
    context = f"function {function['id']}"
    inputs = function["inputs"]
    outputs = function["outputs"]
    raw_nodes = _list(function.get("nodes", []), f"{context}.nodes")
    nodes: dict[str, dict[str, Any]] = {}
    node_inputs: dict[str, list[str]] = {}
    node_outputs: dict[str, list[str]] = {}

    for index, raw in enumerate(raw_nodes):
        node_context = f"{context}.nodes[{index}]"
        if not isinstance(raw, dict):
            raise FlowCompileError(f"{node_context} must be an object")
        node_id = _identifier(raw.get("id"), f"{node_context}.id")
        if node_id in nodes:
            raise FlowCompileError(f"{context} contains duplicate node id {node_id}")
        kind = raw.get("type")
        if kind == "operator":
            _dotted_name(raw.get("callable"), f"{node_context}.callable")
            in_ports = [_identifier(v, f"{node_context}.inputs") for v in _list(raw.get("inputs", []), f"{node_context}.inputs")]
            out_ports = [_identifier(v, f"{node_context}.outputs") for v in _list(raw.get("outputs", []), f"{node_context}.outputs")]
        elif kind == "call":
            target = raw.get("function")
            if target not in functions:
                raise FlowCompileError(f"{node_context}.function references unknown function {target!r}")
            in_ports = [port["id"] for port in functions[target]["inputs"]]
            out_ports = [port["id"] for port in functions[target]["outputs"]]
        else:
            raise FlowCompileError(f"{node_context}.type must be 'operator' or 'call'")
        if len(set(in_ports)) != len(in_ports) or len(set(out_ports)) != len(out_ports):
            raise FlowCompileError(f"{node_context} contains duplicate ports")
        nodes[node_id] = raw
        node_inputs[node_id] = in_ports
        node_outputs[node_id] = out_ports

    connections = _list(function.get("connections", []), f"{context}.connections")
    incoming: dict[Endpoint, Endpoint] = {}
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    input_ids = {port["id"] for port in inputs}
    output_ids = {port["id"] for port in outputs}
    for index, raw in enumerate(connections):
        connection_context = f"{context}.connections[{index}]"
        if not isinstance(raw, dict):
            raise FlowCompileError(f"{connection_context} must be an object")
        source = _endpoint(raw.get("from"), f"{connection_context}.from")
        target = _endpoint(raw.get("to"), f"{connection_context}.to")
        if source.node == "$output" or target.node == "$input":
            raise FlowCompileError(f"{connection_context} has a reversed endpoint")
        if source.node == "$input":
            if source.port not in input_ids:
                raise FlowCompileError(f"{connection_context} references unknown input port")
        elif source.node not in nodes or source.port not in node_outputs[source.node]:
            raise FlowCompileError(f"{connection_context} references unknown source port")
        if target.node == "$output":
            if target.port not in output_ids:
                raise FlowCompileError(f"{connection_context} references unknown output port")
        elif target.node not in nodes or target.port not in node_inputs[target.node]:
            raise FlowCompileError(f"{connection_context} references unknown target port")
        if target in incoming:
            raise FlowCompileError(f"{connection_context} connects an input more than once")
        incoming[target] = source
        if source.node in nodes and target.node in nodes:
            dependencies[target.node].add(source.node)

    required = [Endpoint(node_id, port) for node_id, ports in node_inputs.items() for port in ports]
    required += [Endpoint("$output", port["id"]) for port in outputs]
    missing = [endpoint for endpoint in required if endpoint not in incoming]
    if missing:
        endpoint = missing[0]
        raise FlowCompileError(f"{context} input {endpoint.node}.{endpoint.port} is not connected")

    ready = sorted(node_id for node_id, deps in dependencies.items() if not deps)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for candidate in sorted(dependencies):
            if node_id in dependencies[candidate]:
                dependencies[candidate].remove(node_id)
                if not dependencies[candidate] and candidate not in order and candidate not in ready:
                    ready.append(candidate)
                    ready.sort()
    if len(order) != len(nodes):
        raise FlowCompileError(f"{context} contains a cycle")

    input_variables = {port["id"]: port["name"] for port in inputs}
    variables: dict[Endpoint, str] = {}
    used_variables = set(input_variables.values())

    def source_expression(endpoint: Endpoint) -> str:
        source = incoming[endpoint]
        if source.node == "$input":
            return input_variables[source.port]
        return variables[source]

    body: list[str] = []
    for node_id in order:
        node = nodes[node_id]
        args = [source_expression(Endpoint(node_id, port)) for port in node_inputs[node_id]]
        kwargs = node.get("kwargs", {})
        if not isinstance(kwargs, dict):
            raise FlowCompileError(f"{context}.nodes[{node_id}].kwargs must be an object")
        keyword_args = [f"{_identifier(key, f'{context}.nodes[{node_id}].kwargs') }={_literal(value, context)}" for key, value in kwargs.items()]
        if node["type"] == "operator":
            callable_name = node["callable"]
            if "config" in node:
                config_name = node["config"]
                if not isinstance(config_name, str) or not config_name:
                    raise FlowCompileError(
                        f"{context}.nodes[{node_id}].config must be a non-empty string"
                    )
                args.insert(0, f"config({config_name!r})")
        else:
            callable_name = functions[node["function"]]["name"]
        call = f"{callable_name}({', '.join([*args, *keyword_args])})"
        output_variables: list[str] = []
        for port in node_outputs[node_id]:
            base = f"_{node_id}_{port}"
            variable = base
            suffix = 2
            while variable in used_variables:
                variable = f"{base}_{suffix}"
                suffix += 1
            used_variables.add(variable)
            variables[Endpoint(node_id, port)] = variable
            output_variables.append(variable)
        if not output_variables:
            body.append(call)
        elif len(output_variables) == 1:
            body.append(f"{output_variables[0]} = {call}")
        else:
            body.append(f"{', '.join(output_variables)} = {call}")

    params = ", ".join(f"{port['name']}: {port['type']}" for port in inputs)
    if not outputs:
        return_type = "None"
    elif len(outputs) == 1:
        return_type = outputs[0]["type"]
    else:
        return_type = "Tuple[" + ", ".join(port["type"] for port in outputs) + "]"
    if not outputs:
        body.append("return None")
    else:
        values = [source_expression(Endpoint("$output", port["id"])) for port in outputs]
        body.append("return " + (values[0] if len(values) == 1 else ", ".join(values)))
    return ["@workflow", f"def {function['name']}({params}) -> {return_type}:", *[f"    {line}" for line in body]]


def compile_flow_file(path: str | os.PathLike[str], output_path: str | os.PathLike[str] | None = None) -> str:
    """Compile *path*, write a cached sibling ``.flow.py``, and return its path."""
    source_path = Path(path).resolve()
    if source_path.suffix.lower() != ".flow":
        raise FlowCompileError(f"expected a .flow file, got {source_path.name}")
    try:
        raw = source_path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlowCompileError(f"failed to read {source_path.name}: {exc}") from exc
    source = compile_flow_data(data, str(source_path))
    digest = hashlib.sha256(raw).hexdigest()
    source = f"# flow-sha256: {digest}\n" + source
    destination = Path(output_path).resolve() if output_path else source_path.with_suffix(".flow.py")
    if not destination.exists() or destination.read_text(encoding="utf-8") != source:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_text(source, encoding="utf-8", newline="\n")
        os.replace(temporary, destination)
    return str(destination)
