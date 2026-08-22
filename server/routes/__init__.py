"""FastAPI 路由模块集合。

每个路由模块只声明对应领域的 ``APIRouter``，服务实例统一从
``request.app.state`` 获取，便于测试注入。
"""

from . import (  # noqa: F401
    config_routes,
    extension_routes,
    file_routes,
    model_routes,
    script_routes,
    ui_state_routes,
    websocket_routes,
)
