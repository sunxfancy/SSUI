# `.flow` workflow format

SSUI treats a `.flow` file as a versioned JSON graph. The server compiles the
graph to a sibling `<name>.flow.py` file whenever the Functional UI inspects,
prepares, or executes it. Generated files are cache artifacts and are ignored
by Git.

The minimal document contains one workflow whose input is connected directly
to its output:

```json
{
  "version": 1,
  "imports": [],
  "functions": [{
    "id": "identity",
    "name": "identity",
    "inputs": [{ "id": "value", "name": "value", "type": "str" }],
    "outputs": [{ "id": "result", "name": "result", "type": "str" }],
    "nodes": [],
    "connections": [{
      "from": { "node": "$input", "port": "value" },
      "to": { "node": "$output", "port": "result" }
    }]
  }]
}
```

## Operators

An operator invokes an imported Python callable. Inputs are positional and
follow the order in `inputs`; one or more outputs are assigned in `outputs`
order. `kwargs` contains JSON literal keyword arguments. When `config` is
present, `config("...")` is inserted as the first positional argument so the
existing SSUI node configuration system remains available.

```json
{
  "version": 1,
  "imports": [{ "module": "ssui", "names": ["Prompt"] }],
  "functions": [{
    "id": "make_prompt",
    "name": "make_prompt",
    "inputs": [{ "id": "text", "name": "text", "type": "str" }],
    "outputs": [{ "id": "prompt", "name": "prompt", "type": "Prompt" }],
    "nodes": [{
      "id": "create",
      "type": "operator",
      "callable": "Prompt.create",
      "inputs": ["text"],
      "outputs": ["prompt"]
    }],
    "connections": [
      { "from": { "node": "$input", "port": "text" }, "to": { "node": "create", "port": "text" } },
      { "from": { "node": "create", "port": "prompt" }, "to": { "node": "$output", "port": "prompt" } }
    ]
  }]
}
```

Use a `call` node to invoke another function in the same document:

```json
{ "id": "step", "type": "call", "function": "make_prompt" }
```

Its ports are the referenced function's input and output IDs. `$input` and
`$output` are reserved endpoint node IDs. Every node input and workflow output
must have exactly one incoming connection. Cyclic graphs, missing ports,
duplicate identifiers, and unsafe type syntax fail compilation before any
Python is executed.

To compile explicitly, call:

```text
POST /api/flow/compile?flow_path=<absolute-or-project-relative-path>
```

Normal `/api/script`, `/api/prepare`, and `/api/execute` calls also compile a
`.flow` path automatically, so callers do not need to manage the generated
Python file.

## Python operator discovery

The Flow editor discovers callable nodes through:

```text
GET /api/flow/operators?flow_path=<path>
```

Discovery parses source with Python's AST and never imports or executes the
candidate files. It includes public, fully annotated functions from `.py`
files beside the flow, plus public functions and model `load()` methods from
installed `ssui_*` extension packages. Parameters named `config` are supplied
by the SSUI runtime and are not exposed as graph ports.

Sibling filenames must be valid Python module names (for example
`image_tools.py`, not `image-tools.py`). In the serialized flow, represent a
discovered callable with an ordinary `imports` entry and operator node. The
executor permits imports only from valid sibling modules
and its existing extension allowlist.
