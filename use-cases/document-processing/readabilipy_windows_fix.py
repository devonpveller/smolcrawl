"""
Fix for readabilipy Node.js detection on Windows
This module monkey-patches readabilipy to properly detect Node.js on Windows
by using shell=True in subprocess calls.
"""

import subprocess
import os
import readabilipy.utils
import readabilipy.simple_json


def _patched_have_npm():
    """Patched version of have_npm that works on Windows"""
    try:
        cp = subprocess.run(
            ["npm", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            shell=True  # This is the key fix for Windows
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return cp.returncode == 0


def _patched_run_npm_install():
    """Patched version of run_npm_install that works on Windows"""
    import readabilipy.simple_json
    
    # Get the javascript directory path
    jsdir = os.path.join(os.path.dirname(readabilipy.simple_json.__file__), 'javascript')
    
    try:
        subprocess.run(
            ["npm", "install"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            shell=True,  # This is the key fix for Windows
            cwd=jsdir  # Run in the javascript directory where package.json is
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _patched_have_node():
    """Check that we can run node and have a new enough version (Windows-compatible)"""
    try:
        cp = subprocess.run(
            ['node', '-v'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=False,
            shell=True  # This is the key fix for Windows
        )
    except FileNotFoundError:
        return False
    if not cp.returncode == 0:
        return False
    major = int(cp.stdout.split(b'.')[0].lstrip(b'v'))
    if major < 10:
        return False
    # check that this package has a node_modules dir in the javascript
    # directory, if it doesn't, it wasn't installed with Node support
    jsdir = os.path.join(os.path.dirname(readabilipy.simple_json.__file__), 'javascript')
    node_modules = os.path.join(jsdir, 'node_modules')
    if not os.path.exists(node_modules):
        # Try installing node dependencies.
        readabilipy.simple_json.run_npm_install()
    return os.path.exists(node_modules)


# Apply the monkey patches
readabilipy.utils.have_npm = _patched_have_npm
readabilipy.utils.run_npm_install = _patched_run_npm_install
readabilipy.simple_json.have_node = _patched_have_node
readabilipy.simple_json.run_npm_install = _patched_run_npm_install

print("Applied Windows fix for readabilipy Node.js detection")
