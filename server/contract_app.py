"""Lightweight FastAPI application used to export the public API contract.

Unlike ``server.app``, this module does not construct model/executor services or
run extension discovery, so schema generation does not require a GPU runtime.
"""

from fastapi import FastAPI

from server.routes import (
    config_routes,
    extension_routes,
    file_routes,
    model_routes,
    script_routes,
    task_routes,
    ui_state_routes,
)


def create_contract_app() -> FastAPI:
    app = FastAPI(title="SSUI API", version="1.0.0")
    app.include_router(config_routes.router)
    app.include_router(model_routes.router)
    app.include_router(script_routes.router)
    app.include_router(file_routes.router)
    app.include_router(ui_state_routes.router)
    app.include_router(extension_routes.router)
    app.include_router(task_routes.router)
    return app


app = create_contract_app()
