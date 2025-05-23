import argparse
import uvicorn
import os
from server.server import app

def main():
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=7422)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.dev)

if __name__ == "__main__":
    main()
