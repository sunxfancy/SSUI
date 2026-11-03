"""Project API -> MCP schemas. No engine imports and no arbitrary HTTP proxy."""
import base64
import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator, ValidationError
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import Tool, ToolAnnotations, TextContent, CallToolResult


def schema_refs(value):
    if isinstance(value, dict):
        return {key: (item.replace("#/components/schemas/", "#/$defs/")
                      if key == "$ref" else schema_refs(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [schema_refs(item) for item in value]
    return value


class APICatalog:
    def __init__(self, document):
        self.operations = {}
        self.definitions = schema_refs(document.get("components", {}).get("schemas", {}))
        for path, item in document.get("paths", {}).items():
            for method, operation in item.items():
                if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
                    continue
                suffix = re.sub(r"[^a-zA-Z0-9_]", "_", operation.get("operationId", method + path))
                digest = hashlib.sha256((method + path).encode()).hexdigest()[:8]
                name = "ssui_api_" + suffix[:45] + "_" + digest
                props, required = {}, []
                parameters = [*item.get("parameters", []), *operation.get("parameters", [])]
                for group, location in (("path", "path"), ("query", "query"), ("headers", "header")):
                    group_props, group_required = {}, []
                    for param in parameters:
                        if param.get("in") != location:
                            continue
                        group_props[param["name"]] = schema_refs(param.get("schema", {}))
                        if param.get("required"):
                            group_required.append(param["name"])
                    if group_props:
                        props[group] = {"type": "object", "properties": group_props,
                                        "required": group_required, "additionalProperties": False}
                        if group_required:
                            required.append(group)
                body = operation.get("requestBody", {})
                content = body.get("content", {})
                media = next((kind for kind in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded") if kind in content), None)
                if media:
                    body_schema = schema_refs(content[media].get("schema", {}))
                    if media == "multipart/form-data":
                        body_schema = copy.deepcopy(self._dereference(body_schema))
                        for key, field in body_schema.get("properties", {}).items():
                            if field.get("format") == "binary" or field.get("contentMediaType"):
                                body_schema["properties"][key] = {"type": "object", "properties": {
                                    "filename": {"type": "string"}, "data_base64": {"type": "string", "maxLength": 28000000},
                                    "content_type": {"type": "string", "default": "application/octet-stream"}},
                                    "required": ["filename", "data_base64"], "additionalProperties": False}
                    props["body"] = body_schema
                    if body.get("required"):
                        required.append("body")
                schema = {"type": "object", "properties": props, "required": required,
                          "additionalProperties": False}
                reachable = {}
                def collect(value):
                    if isinstance(value, dict):
                        ref = value.get("$ref", "")
                        if ref.startswith("#/$defs/"):
                            key = ref.rsplit("/", 1)[-1]
                            if key not in reachable:
                                reachable[key] = self.definitions[key]
                                collect(reachable[key])
                        for nested in value.values():
                            collect(nested)
                    elif isinstance(value, list):
                        for nested in value:
                            collect(nested)
                collect(schema)
                if reachable:
                    schema["$defs"] = reachable
                description = f"{method.upper()} {path}. " + operation.get("description", operation.get("summary", "SSUI API"))
                if path.startswith("/api/generation/"):
                    description += " Prototype/mock generation only; use script execution for real models."
                self.operations[name] = {"path": path, "method": method.upper(), "media": media,
                    "tool": Tool(name=name, description=description,
                                 inputSchema=schema, annotations=ToolAnnotations(
                                     readOnlyHint=method in ("get", "head") and path != "/api/script",
                                     destructiveHint=method not in ("get", "head"), openWorldHint=True))}

    def _dereference(self, schema):
        if "$ref" in schema:
            return self.definitions[schema["$ref"].rsplit("/", 1)[-1]]
        return schema

    def prepare(self, name, arguments):
        operation = self.operations[name]
        try:
            Draft202012Validator(operation["tool"].inputSchema).validate(arguments)
        except ValidationError as exc:
            raise ToolError(f"Invalid API arguments: {exc.message}") from exc
        path = operation["path"]
        for key, value in arguments.get("path", {}).items():
            path = path.replace("{" + key + "}", quote(str(value), safe=""))
        # Do not allow path arguments to reinterpret the registered route.
        if any(str(value) in (".", "..") for value in arguments.get("path", {}).values()):
            raise ToolError("Dot path segments are not allowed")
        kwargs = {"params": arguments.get("query", {}), "headers": arguments.get("headers", {})}
        body = arguments.get("body")
        if operation["media"] == "application/json" and "body" in arguments:
            kwargs["json"] = body
        elif operation["media"] == "application/x-www-form-urlencoded":
            kwargs["data"] = body
        elif operation["media"] == "multipart/form-data":
            files, data = {}, {}
            for key, value in (body or {}).items():
                if isinstance(value, dict) and "data_base64" in value:
                    try:
                        decoded = base64.b64decode(value["data_base64"], validate=True)
                    except ValueError as exc:
                        raise ToolError("Upload data_base64 is not valid base64") from exc
                    files[key] = (value["filename"], decoded, value.get("content_type", "application/octet-stream"))
                else:
                    data[key] = value
            kwargs.update(files=files, data=data)
        return operation["method"], path, kwargs


class CatalogMCP(FastMCP):
    """Keep focused workflow tools and expose every registered HTTP operation."""
    catalog = None
    schema_source = "not loaded"

    async def refresh_catalog(self):
        try:
            document = await self.api_request("GET", "/openapi.json")
            if not isinstance(document.get("paths"), dict):
                raise ToolError("Backend did not return an OpenAPI document")
            self.schema_source = "live backend"
        except ToolError:
            document = json.loads(Path(__file__).with_name("openapi.json").read_text(encoding="utf-8"))
            self.schema_source = "bundled fallback; backend unavailable or invalid"
        self.catalog = APICatalog(document)

    async def list_tools(self):
        if self.catalog is None:
            await self.refresh_catalog()
        return [*await super().list_tools(), *(op["tool"] for op in self.catalog.operations.values())]

    async def call_tool(self, name, arguments):
        if name.startswith("ssui_api_"):
            if self.catalog is None:
                await self.refresh_catalog()
            if name not in self.catalog.operations:
                raise ToolError("Unknown API tool; refresh the capability catalog")
            method, path, kwargs = self.catalog.prepare(name, arguments)
            result = await self.api_request(method, path, raw=True, **kwargs)
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
                                  structuredContent={"result": result})
        return await super().call_tool(name, arguments)
