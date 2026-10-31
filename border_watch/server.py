"""Local web server: static dashboard, JSON API (login + roles), MJPEG streams, video upload, event replay."""
import json, os, re, secrets, time, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from .engine import Engine
from .db import ROLES

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
PUBLIC = {"/", "/index.html", "/app.js", "/style.css", "/api/login", "/api/me"}
VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv")
SESSION_SECONDS = 12 * 3600

def make_handler(eng, require_login=True):
    sessions, fails = {}, {}
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a): pass
        def _send(self, body, ctype="application/json", code=200, extra=None):
            b = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else str(body)).encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(b)
        # ---- auth ----
        def _session(self):
            if not require_login: return dict(user="admin", role="admin", must_change=False)
            m = re.search(r"bw_session=([A-Za-z0-9_\-]+)", self.headers.get("Cookie", ""))
            s = sessions.get(m.group(1)) if m else None
            if s and s["exp"] > time.time(): return s
            return None
        def _need(self, level=0):
            s = self._session()
            if not s: self._send({"ok": False, "msg": "Please sign in.", "login": True}, code=401); return None
            if ROLES[s["role"]] < level: self._send({"ok": False, "msg": "Your role does not allow this action."}, code=403); return None
            return s
        def _login(self, body):
            ip = self.client_address[0]; f = fails.get(ip, (0, 0))
            if f[1] > time.time(): return self._send({"ok": False, "msg": "Too many attempts. Wait 30 seconds."}, code=429)
            u = eng.db.verify(str(body.get("username", "")), str(body.get("password", "")))
            if not u:
                n = f[0] + 1; fails[ip] = (n, time.time() + 30 if n >= 5 else 0)
                eng.say(f"Failed login for '{str(body.get('username', ''))[:30]}'."); return self._send({"ok": False, "msg": "Wrong username or password."}, code=401)
            fails.pop(ip, None); tok = secrets.token_urlsafe(32); sessions[tok] = dict(user=u["user"], role=u["role"], must_change=u["must_change"], exp=time.time() + SESSION_SECONDS)
            eng.say("Signed in.", u["user"])
            self._send(dict(ok=True, **u), extra={"Set-Cookie": f"bw_session={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}"})
        # ---- GET ----
        def do_GET(self):
            u = urllib.parse.urlparse(self.path); p = u.path
            try:
                if p == "/api/me":
                    s = self._session()
                    return self._send(dict(ok=bool(s), login_required=require_login, **(dict(user=s["user"], role=s["role"], must_change=s["must_change"]) if s else {})))
                if p not in PUBLIC and p.startswith("/api/") and not self._need(0): return
                if p == "/api/state":
                    s = self._session(); st = eng.state(); st.update(user=s["user"], role=s["role"], must_change=s["must_change"]); return self._send(st)
                if p == "/api/report.csv": return self._send(eng.store.csv(), "text/csv", extra={"Content-Disposition": "attachment; filename=border_watch_events.csv"})
                if p == "/api/report.html": return self._send(eng.store.report_html(eng.kpis(), eng.thumbs()), "text/html; charset=utf-8")
                if p == "/api/users":
                    return self._send(eng.db.users()) if self._need(2) else None
                if p == "/api/audit":
                    return self._send(eng.db.audit(200)) if self._need(2) else None
                m = re.fullmatch(r"/api/(stream|snapshot|frame)/(CAM-0[1-5])", p)
                if m:
                    cw = eng.cams.get(m.group(2))
                    if not cw: return self._send({"error": "video unavailable"}, code=404)
                    if m.group(1) in ("frame", "snapshot"):
                        if not cw.jpeg: return self._send({"error": "no frame"}, code=404)
                        return self._send(cw.jpeg, "image/jpeg", extra={"Cache-Control": "no-store", **({"Content-Disposition": f"attachment; filename={m.group(2)}.jpg"} if m.group(1) == "snapshot" else {})})
                    return self._stream(cw)
                m = re.fullmatch(r"/api/heat/(CAM-0[1-5])\.jpg", p)
                if m:
                    j = eng.heat_jpeg(m.group(1)); return self._send(j, "image/jpeg", extra={"Cache-Control": "no-store"}) if j else self._send({"error": "no data"}, code=404)
                m = re.fullmatch(r"/api/evidence/(\d+)\.jpg", p)
                if m:
                    f = os.path.join(eng.data, "evidence", m.group(1) + ".jpg")
                    return self._send(open(f, "rb").read(), "image/jpeg") if os.path.exists(f) else self._send({"error": "no evidence"}, code=404)
                m = re.fullmatch(r"/api/clip/(\d+)(?:/(\d+)\.jpg)?", p)
                if m:
                    d = os.path.join(eng.data, "clips", m.group(1))
                    if m.group(2) is None:
                        n = len([x for x in os.listdir(d) if x.endswith(".jpg")]) if os.path.isdir(d) else 0
                        return self._send(dict(n=n, fps=6))
                    f = os.path.join(d, f"{int(m.group(2)):03d}.jpg")
                    return self._send(open(f, "rb").read(), "image/jpeg", extra={"Cache-Control": "max-age=3600"}) if os.path.exists(f) else self._send({"error": "no frame"}, code=404)
                name = "index.html" if p in ("/", "") else p.lstrip("/")
                f = os.path.normpath(os.path.join(WEB, name))
                if f.startswith(WEB) and os.path.isfile(f) and not name.startswith("standalone"):
                    return self._send(open(f, "rb").read(), TYPES.get(os.path.splitext(f)[1], "application/octet-stream"), extra={"Cache-Control": "no-cache"})
                self._send({"error": "not found"}, code=404)
            except (BrokenPipeError, ConnectionResetError): pass
        def _stream(self, cw):
            self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store"); self.send_header("Connection", "close"); self.end_headers()
            gen, last = cw.gen, None
            try:
                while gen == cw.gen:
                    j = cw.jpeg
                    if j is not None and j is not last:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(j) + j + b"\r\n"); last = j
                    time.sleep(0.04)
            except (BrokenPipeError, ConnectionResetError, OSError): pass
            self.close_connection = True
        # ---- POST ----
        def do_POST(self):
            u = urllib.parse.urlparse(self.path); n = int(self.headers.get("Content-Length", 0)); p = u.path
            try:
                if p == "/api/login": return self._login(json.loads(self.rfile.read(n) or b"{}"))
                if p == "/api/logout":
                    m = re.search(r"bw_session=([A-Za-z0-9_\-]+)", self.headers.get("Cookie", "")); sessions.pop(m.group(1), None) if m else None
                    return self._send(dict(ok=True), extra={"Set-Cookie": "bw_session=; Max-Age=0; Path=/"})
                s = self._need(0)
                if not s: return
                if p == "/api/upload":
                    if ROLES[s["role"]] < 1: return self._send({"ok": False, "msg": "Your role does not allow uploads."}, code=403)
                    q = urllib.parse.parse_qs(u.query); cam = q.get("cam", [""])[0]; name = os.path.basename(q.get("name", ["video.mp4"])[0])
                    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:80] or "video.mp4"
                    if os.path.splitext(safe)[1].lower() not in VIDEO_EXT or cam not in eng.cams:
                        return self._send({"ok": False, "msg": "Please upload a video file (mp4, avi, mov, mkv, webm) to a valid camera."}, code=400)
                    path = os.path.join(eng.data, "uploads", f"{cam}_{int(time.time())}_{safe}")
                    with open(path, "wb") as f:
                        left = n
                        while left > 0:
                            chunk = self.rfile.read(min(left, 1 << 20))
                            if not chunk: break
                            f.write(chunk); left -= len(chunk)
                    return self._send(eng.add_upload(cam, name, path, s["user"]))
                body = json.loads(self.rfile.read(n) or b"{}")
                if p == "/api/ask": return self._send({"answer": eng.ask(str(body.get("q", "")))})
                if p == "/api/cmd":
                    r = eng.command(body, s["user"], s["role"]); return self._send(r, code=200 if r.get("ok") or "role" not in r.get("msg", "") else 403)
                if p == "/api/password":
                    v = eng.db.verify(s["user"], str(body.get("old", "")))
                    if not v: return self._send({"ok": False, "msg": "Current password is wrong."}, code=400)
                    eng.db.set_password(s["user"], str(body.get("new", ""))); s["must_change"] = False; eng.say("Password changed.", s["user"]); return self._send({"ok": True})
                if p == "/api/users":
                    if not self._need(2): return
                    try:
                        if body.get("op") == "add": eng.db.add_user(str(body["username"]), str(body["password"]), str(body.get("role", "viewer"))); eng.say(f"User '{body['username']}' created ({body.get('role', 'viewer')}).", s["user"])
                        elif body.get("op") == "delete":
                            if body["username"] == s["user"]: raise ValueError("You cannot delete yourself.")
                            eng.db.delete_user(str(body["username"])); eng.say(f"User '{body['username']}' deleted.", s["user"])
                        else: raise ValueError("Unknown operation.")
                    except ValueError as ex: return self._send({"ok": False, "msg": str(ex)}, code=400)
                    return self._send({"ok": True, "users": eng.db.users()})
                self._send({"error": "not found"}, code=404)
            except (BrokenPipeError, ConnectionResetError): pass
            except Exception as ex: self._send({"ok": False, "msg": str(ex)}, code=400)
    return H

def serve(port=8000, seed=None, backend="auto", model="", host="127.0.0.1", login=True, imgsz=None):
    eng = Engine(seed, backend, model, imgsz)
    srv = ThreadingHTTPServer((host, port), make_handler(eng, login)); srv.daemon_threads = True
    print(f"Border Watch running at http://localhost:{port}   (Ctrl+C to stop)")
    if login: print("Sign in with  admin / admin  on first run (you will be asked to change the password).")
    else: print("WARNING: login is disabled (--no-login). Use only on a trusted machine.")
    if host not in ("127.0.0.1", "localhost"): print("WARNING: listening on the network over plain HTTP. Put it behind HTTPS (reverse proxy) before real use.")
    if not eng.cams: print("Note: OpenCV is not installed, so video is disabled. Run: pip install opencv-python-headless")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")
