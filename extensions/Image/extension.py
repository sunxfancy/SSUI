import os
import ssui_image

from fastapi import Request, APIRouter
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = APIRouter()

@app.get("/version")
async def version():
    print("获取图片扩展版本")
    return {"version": "0.0.1"}

@app.get("/canvas/", response_class=RedirectResponse)
async def root(request: Request):
    query_string = request.url.query
    # TODO: 想办法去掉extension/ImageExtension/这个前缀
    redirect_url = "/extension/ImageExtension/canvas/index.html"
    if query_string:
        redirect_url += f"?{query_string}"
    return RedirectResponse(url=redirect_url)
