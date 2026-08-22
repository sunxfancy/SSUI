import os

from fastapi import APIRouter, Body, File, Request, UploadFile
from fastapi.responses import FileResponse

from ss_executor import search_project_root

router = APIRouter()

EXT_NAME_MAP = {
    "image": ("png", "jpg", "jpeg", "bmp"),
    "video": ("mp4", "avi", "mov", "mkv"),
    "audio": ("mp3", "wav", "m4a", "ogg"),
    "3dmodel": ("obj", "fbx", "glb", "gltf"),
    "script": ("py",),
}


@router.get("/file/root_path")
async def root_path(script_path: str):
    return search_project_root(script_path)


@router.get("/files/{file_type}")
async def files(file_type: str, script_path: str):
    project_root = search_project_root(script_path)
    if project_root is None:
        return {"error": "Project root not found"}

    # TODO: 也许对于日后大目录来说，需要考虑性能问题，但我决定遇到了再说
    result_files = []
    for root, dirs, filenames in os.walk(project_root):
        for filename in filenames:
            if filename.endswith(EXT_NAME_MAP[file_type]):
                result_files.append(os.path.join(root, filename))
    return result_files


@router.post("/files/upload")
async def upload_file(script_path: str, file: UploadFile = File(...)):
    project_root = search_project_root(script_path)
    if project_root is None:
        return {"error": "Project root not found"}

    input_dir = os.path.join(project_root, "input")
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)

    file_path = os.path.join(input_dir, file.filename)
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        return {"success": True, "path": file_path}
    except Exception as e:
        return {"error": str(e)}


@router.post("/files/upload_json")
async def file_upload_json(
    path: str = Body(..., embed=True),
    content: str = Body(..., embed=True),
):
    try:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@router.get("/file")
async def file(path: str):
    print("access file: ", path)
    if os.path.exists(path):
        headers = {"Cache-Control": "no-store"}
        if path.endswith(".png"):
            return FileResponse(path, media_type="image/png", headers=headers)
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            return FileResponse(path, media_type="image/jpeg", headers=headers)
        elif path.endswith(".json"):
            return FileResponse(path, media_type="application/json", headers=headers)
        else:
            return FileResponse(path, headers=headers)
    return None
