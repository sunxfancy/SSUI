
from typing import List, Optional
from server import SSUIServer
import asyncio
import argparse
import logging
import os

parser = argparse.ArgumentParser()

parser.add_argument("--listen", type=str, default="127.0.0.1", metavar="IP", nargs="?", const="0.0.0.0,::", help="Specify the IP address to listen on (default: 127.0.0.1). You can give a list of ip addresses by separating them with a comma like: 127.2.2.2,127.3.3.3 If --listen is provided without an argument, it defaults to 0.0.0.0,:: (listens on all ipv4 and ipv6)")
parser.add_argument("--port", type=int, default=8188, help="Set the listen port.")
parser.add_argument("--tls-keyfile", type=str, help="Path to TLS (SSL) key file. Enables TLS, makes app accessible at https://... requires --tls-certfile to function")
parser.add_argument("--tls-certfile", type=str, help="Path to TLS (SSL) certificate file. Enables TLS, makes app accessible at https://... requires --tls-keyfile to function")
parser.add_argument("--enable-cors-header", type=str, default=None, metavar="ORIGIN", nargs="?", const="*", help="Enable CORS (Cross-Origin Resource Sharing) with optional origin or allow all with default '*'.")
parser.add_argument("--max-upload-size", type=float, default=100, help="Set the maximum upload size in MB.")

parser.add_argument("--extra-model-paths-config", type=str, default=None, metavar="PATH", nargs='+', action='append', help="Load one or more extra_model_paths.yaml files.")
parser.add_argument("--output-directory", type=str, default=None, help="Set the ComfyUI output directory.")
parser.add_argument("--temp-directory", type=str, default=None, help="Set the ComfyUI temp directory (default is in the ComfyUI directory).")
parser.add_argument("--input-directory", type=str, default=None, help="Set the ComfyUI input directory.")
parser.add_argument("--auto-launch", default=True, action="store_true", help="Automatically launch ComfyUI in the default browser.")
parser.add_argument("--disable-auto-launch", action="store_true", help="Disable auto launching the browser.")
parser.add_argument("--cuda-device", type=int, default=None, metavar="DEVICE_ID", help="Set the id of the cuda device this instance will use.")
cm_group = parser.add_mutually_exclusive_group()
cm_group.add_argument("--cuda-malloc", action="store_true", help="Enable cudaMallocAsync (enabled by default for torch 2.0 and up).")
cm_group.add_argument("--disable-cuda-malloc", action="store_true", help="Disable cudaMallocAsync.")


# The default built-in provider hosted under web/
DEFAULT_VERSION_STRING = "SSUI@latest"

parser.add_argument(
    "--front-end-version",
    type=str,
    default=DEFAULT_VERSION_STRING,
    help="""
    Specifies the version of the frontend to be used. This command needs internet connectivity to query and
    download available frontend implementations from GitHub releases.

    The version string should be in the format of:
    [repoOwner]/[repoName]@[version]
    where version is one of: "latest" or a valid version number (e.g. "1.0.0")
    """,
)

def is_valid_directory(path: Optional[str]) -> Optional[str]:
    """Validate if the given path is a directory."""
    if path is None:
        return None

    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"{path} is not a valid directory.")
    return path

parser.add_argument(
    "--front-end-root",
    type=is_valid_directory,
    default=None,
    help="The local filesystem path to the directory where the frontend is located. Overrides --front-end-version.",
)

parser.add_argument("--user-directory", type=is_valid_directory, default=None, help="Set the ComfyUI user directory with an absolute path.")
args = parser.parse_args()


async def run(server):
    await asyncio.gather(server.start(), server.loop())

def main():
    
    try:
        server = SSUIServer(address=args.listen, port=args.port, verbose=True)
        if args.auto_launch:
            def startup_server(scheme, address, port):
                import webbrowser
                if os.name == 'nt' and address == '0.0.0.0':
                    address = '127.0.0.1'
                if ':' in address:
                    address = "[{}]".format(address)
                webbrowser.open(f"{scheme}://{address}:{port}")
            server.on_start = startup_server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run(server))
    except KeyboardInterrupt:
        logging.info("\nStopped server")


if __name__ == "__main__":
    main() 