"""Install trusted extension roots before third-party site-packages."""
import os
import sys


def add_extension_path(directory):
    # Add only package roots: recursively adding vendor children shadows unrelated
    # modules such as onnx and bypasses their package initialization.
    roots = [os.path.abspath(directory)]
    vendor = os.path.join(roots[0], "vendor")
    if os.path.isdir(vendor):
        roots.append(vendor)
    for root in reversed(roots):
        while root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)
