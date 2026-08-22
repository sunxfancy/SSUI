"""FastAPI 应用入口。

路由与依赖注入统一在 :func:`server.app.create_app` 中组装，
此处保留模块级 ``app`` 实例以兼容 ``python -m server`` 与既有导入。
"""

from server.app import create_app

app = create_app()

