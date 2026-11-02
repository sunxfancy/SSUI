from copy import deepcopy


BASE_TASK = {
    "id": "task-1",
    "kind": "generation",
    "name": "Mock image generation",
    "status": "waiting",
    "progress": 0,
    "createdAt": 1_700_000_000,
    "error": None,
    "meta": {"script": "/fixtures/demo.py", "callable": "generate"},
}


def initial_state(name: str = "happy-path") -> dict:
    return {
        "scenario": name,
        "requests": [],
        "tasks": [deepcopy(BASE_TASK)],
        "config": {
            "ui": {
                "theme": "system",
                "auto_open_details": True,
                "external_code_editor": "",
                "civitai_token": "",
            }
        },
    }
