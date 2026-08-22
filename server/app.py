import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from server.config_service import ConfigService
from server.extensions import ExtensionManager
from server.model_service import ModelService
from server.opener_service import FileOpenerManager
from server.routes import (
    config_routes,
    extension_routes,
    file_routes,
    model_routes,
    script_routes,
    ui_state_routes,
    websocket_routes,
)
from server.script_service import ScriptService
from server.websocket_service import WebSocketService
from ss_executor.scheduler import TaskScheduler


def create_app(
    config_service=None,
    model_service=None,
    scheduler=None,
    script_service=None,
    websocket_service=None,
) -> FastAPI:
    """组装 FastAPI 应用。

    所有服务均可通过参数注入（便于测试），默认按生产路径创建。
    路由通过 ``request.app.state`` 访问服务实例。
    """
    resources_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "resources")
    )
    settings_path = os.path.join(resources_dir, "ssui_config.json")

    config_service = config_service or ConfigService(settings_path)
    scheduler = scheduler or TaskScheduler()
    script_service = script_service or ScriptService(scheduler)
    model_service = model_service or ModelService(resources_dir)
    websocket_service = websocket_service or WebSocketService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 检测扩展
        ExtensionManager.instance().detectExtensions(app)
        print("检测扩展完成")
        await scheduler.start()
        yield
        # 关闭所有连接
        print("closing scheduler and all websocket connections.")
        await scheduler.stop()
        websocket_service.stop()

    app = FastAPI(lifespan=lifespan)

    app.state.config_service = config_service
    app.state.model_service = model_service
    app.state.scheduler = scheduler
    app.state.script_service = script_service
    app.state.websocket_service = websocket_service
    app.state.resources_dir = resources_dir
    app.state.settings_path = settings_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(config_routes.router)
    app.include_router(model_routes.router)
    app.include_router(script_routes.router)
    app.include_router(file_routes.router)
    app.include_router(ui_state_routes.router)
    app.include_router(extension_routes.router)
    app.include_router(websocket_routes.router)

    # 对于静态数据的请求，使用文件资源管理器
    settings = config_service.get_settings()
    if settings.host_web_ui:
        web_ui_dir = settings.host_web_ui
        if os.path.isdir(web_ui_dir):

            @app.get("/functional_ui/", response_class=RedirectResponse)
            async def root(request: Request):
                query_string = request.url.query
                redirect_url = "/functional_ui/index.html"
                if query_string:
                    redirect_url += f"?{query_string}"
                return RedirectResponse(url=redirect_url)

            app.mount(
                "/functional_ui/",
                StaticFiles(directory=web_ui_dir),
                name="static",
            )
            print("mount functional_ui", web_ui_dir)
        else:
            print(
                f"警告: functional_ui 目录不存在，跳过挂载（请先构建前端）: {web_ui_dir}"
            )

    FileOpenerManager.instance().register_opener(
        "FunctionalUI", ".py", "/functional_ui/?path="
    )
    FileOpenerManager.instance().register_opener(
        "WorkflowUI", ".flow", "/functional_ui/?view=workflow&path="
    )
    FileOpenerManager.instance().register_opener(
        "ProjectSettings", "ssproject.yaml", "/functional_ui/?view=project_settings&path="
    )
    FileOpenerManager.instance().register_opener(
        "ImagePreview", ".png", "/functional_ui/?view=image_preview&path="
    )

    return app
