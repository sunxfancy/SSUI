import argparse
import uvicorn
import os
from server.server import app

def main():
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    parser.add_argument('--host', type=str, default=None,
                        help="Host to bind (default: $SSUI_SERVER_HOST or localhost)")
    parser.add_argument('--port', type=int, default=None,
                        help="Port to bind (default: $SSUI_SERVER_PORT or 7422)")
    args = parser.parse_args()
    host = args.host or os.environ.get("SSUI_SERVER_HOST", "localhost")
    port = args.port or int(os.environ.get("SSUI_SERVER_PORT", "7422"))
    uvicorn.run(app, host=host, port=port, reload=args.dev)

if __name__ == "__main__":
    main()
