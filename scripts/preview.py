#!/usr/bin/env python3
"""Serve the wvw.dev store front end with this repository's local apps.json.

wvw.dev's build.sh only fetches each store's pushed apps.json from GitHub. This
server runs that same build.sh against the local, unpushed apps.json instead, so
the preview shows what the live store will look like after a push. It rebuilds
whenever apps.json or the wvw.dev build inputs change, and serves this
repository's files under /local-store/ so new screenshots show before a push.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STORE_DIR = Path(__file__).resolve().parent.parent
WVW_DIR = Path(os.environ.get("WVW_DEV_DIR", STORE_DIR.parent / "repos" / "wvw.dev")).resolve()
PORT = int(os.environ.get("PORT", "8080"))
SOURCE = "stedwick/wvw.dev.apps"
LOCAL_URL = f"http://127.0.0.1:{PORT}/local-store/apps.json"
# Links to this repository's files on GitHub resolve to the local copies instead.
RAW_PREFIX = re.compile(rf"^https://raw\.githubusercontent\.com/{re.escape(SOURCE)}/(?:main|master|HEAD)/")
BUILD_INPUTS = [STORE_DIR / "apps.json", WVW_DIR / "build.sh", WVW_DIR / "categories.json", WVW_DIR / "featured.json"]
# Replaces the store's service worker so its caches never hide a local change.
NO_CACHE_SW = b"""self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", () => self.registration.unregister());
"""

build_lock = threading.Lock()
built = {"stamp": None, "body": None, "error": None}


def localize(value):
    if isinstance(value, dict):
        return {k: localize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [localize(v) for v in value]
    if isinstance(value, str):
        return RAW_PREFIX.sub("/local-store/", value)
    return value


def build():
    try:
        json.loads((STORE_DIR / "apps.json").read_text())
    except ValueError as e:
        return None, f"apps.json is not valid JSON: {e}"
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("categories.json", "featured.json"):
            shutil.copy(WVW_DIR / name, tmp)
        Path(tmp, "stores.json").write_text(json.dumps([LOCAL_URL]))
        env = dict(os.environ)
        token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
        if token:
            env["GITHUB_TOKEN"] = token  # avoids GitHub's 60 requests/hour anonymous limit
        result = subprocess.run(["bash", str(WVW_DIR / "build.sh")], cwd=tmp, env=env, stdout=sys.stdout, stderr=sys.stderr)
        if result.returncode != 0:
            return None, f"build.sh exited with {result.returncode}"
        catalog = json.loads(Path(tmp, "apps.json").read_text())
    for app in catalog["apps"]:
        # build.sh names URL sources after the URL; the live store uses the repository path.
        app["_source"], app["_owner"] = SOURCE, SOURCE.split("/")[0]
        # The live build's assets.sh links apps without an icon to wvw.dev's generated one.
        if not app.get("icon") and (WVW_DIR / "assets" / "icons" / f"{app['id']}.jpg").exists():
            app["_generatedIcon"] = f"/assets/icons/{app['id']}.jpg"
    if not catalog["apps"]:
        return None, "the build produced no apps; check the build log"
    return json.dumps(localize(catalog)).encode(), None


def current_catalog():
    with build_lock:
        stamp = tuple(p.stat().st_mtime_ns for p in BUILD_INPUTS)
        if stamp != built["stamp"]:
            print(f"Building catalog from {STORE_DIR / 'apps.json'}", flush=True)
            built["body"], built["error"] = build()
            built["stamp"] = stamp
            print(built["error"] or "Catalog ready", flush=True)
        return built["body"], built["error"]


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def route(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path == "/apps.json":
            body, error = current_catalog()
            if error:
                return self.send_bytes(500, json.dumps({"error": error}).encode(), "application/json")
            return self.send_bytes(200, body, "application/json")
        if path == "/sw.js":
            return self.send_bytes(200, NO_CACHE_SW, "text/javascript")
        if path.startswith("/local-store/"):
            rel = path[len("/local-store/"):]
            if rel.split("/", 1)[0].startswith("."):
                return self.send_bytes(404, b"Not found", "text/plain")
            self.directory = str(STORE_DIR)
            self.path = "/" + rel
            return super().do_GET() if self.command == "GET" else super().do_HEAD()
        if not Path(self.translate_path(path)).exists():
            # GitHub Pages serves 404.html for unknown paths; it redirects clean URLs to the app.
            return self.send_bytes(404, (WVW_DIR / "404.html").read_bytes(), "text/html")
        return super().do_GET() if self.command == "GET" else super().do_HEAD()

    do_GET = route
    do_HEAD = route


if __name__ == "__main__":
    if not (WVW_DIR / "build.sh").exists():
        sys.exit(f"wvw.dev checkout not found at {WVW_DIR}; run scripts/sync-wvw-dev.sh")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), partial(Handler, directory=str(WVW_DIR)))
    # build.sh fetches apps.json from this server, so build only once it is listening.
    threading.Thread(target=current_catalog, daemon=True).start()
    print(f"Serving {WVW_DIR} with {STORE_DIR / 'apps.json'} on port {PORT}", flush=True)
    server.serve_forever()
