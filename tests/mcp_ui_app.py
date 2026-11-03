"""Model-free browser fixture using real production UI, file/state and agent routes."""
import json
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Body, HTTPException
from fastapi.staticfiles import StaticFiles
from server.agent_bridge import router as agent_router
from server.routes.file_routes import router as file_router
from server.routes.ui_state_routes import router as state_router
from server.mcp_server import create_mcp


@asynccontextmanager
async def lifespan(app):
    with tempfile.TemporaryDirectory(prefix='ssui-mcp-ui-') as directory:
        root = Path(directory)
        (root / 'ssproject.yaml').write_text('name: mcp-ui-test\n', encoding='utf-8')
        (root / 'drawing.canvas').write_text('', encoding='utf-8')
        (root / 'workflow.flow').write_text('{}', encoding='utf-8')
        (root / 'script.py').write_text('print("original")\n', encoding='utf-8')
        app.state.root = root
        yield


app = FastAPI(lifespan=lifespan)
app.include_router(agent_router)
app.include_router(file_router)
app.include_router(state_router)
mcp = create_mcp('http://127.0.0.1:17424', timeout=10)


@app.get('/test/files')
async def files():
    return {key: str(app.state.root / name) for key, name in {'canvas': 'drawing.canvas', 'flow': 'workflow.flow', 'code': 'script.py'}.items()}


@app.post('/test/mcp')
async def call(name: str = Body(...), arguments: dict = Body(default_factory=dict)):
    try:
        result = await mcp.call_tool(name, arguments)
        if hasattr(result, 'structuredContent'):
            return result.structuredContent
        if isinstance(result, tuple):
            return result[1]
        return json.loads(result[0].text) if result else None
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/config/')
async def config():
    return {'ui': {'theme': 'light', 'auto_open_details': False, 'external_code_editor': '', 'civitai_token': ''}}


@app.get('/api/flow/operators')
async def operators():
    return {'operators': [], 'errors': []}


root = Path(__file__).resolve().parent.parent
app.mount('/functional_ui', StaticFiles(directory=root / 'frontend/functional_ui/dist', html=True))
app.mount('/extension/ImageExtension/canvas', StaticFiles(directory=root / 'extensions/Image/dist', html=True))
