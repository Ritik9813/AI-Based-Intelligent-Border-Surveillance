"""SQLite storage: users, events, audit log and settings. Standard library only."""
import hashlib, hmac, json, os, secrets, sqlite3, threading, time

ROLES = {"viewer": 0, "operator": 1, "admin": 2}

class DB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False); self.lock = threading.RLock()
        self.c.executescript("""CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT, hash TEXT, role TEXT, must_change INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, data TEXT);
            CREATE TABLE IF NOT EXISTS audit(ts REAL, user TEXT, msg TEXT);
            CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);""")
        if not self.all("SELECT username FROM users"): self.add_user("admin", "admin", "admin", must_change=True)

    def q(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args); self.c.commit(); return cur
    def all(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args); cols = [d[0] for d in cur.description or []]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    # settings
    def get(self, k, default=None):
        r = self.all("SELECT v FROM kv WHERE k=?", (k,)); return json.loads(r[0]["v"]) if r else default
    def put(self, k, v): self.q("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, json.dumps(v)))

    # audit
    def log(self, msg, user=None): self.q("INSERT INTO audit(ts,user,msg) VALUES(?,?,?)", (time.time(), user, msg))
    def audit(self, n=100): return self.all("SELECT ts,user,msg FROM audit ORDER BY ts DESC LIMIT ?", (n,))

    # users
    @staticmethod
    def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    def add_user(self, name, pw, role="viewer", must_change=False):
        name = name.strip()
        if not name or len(name) > 40 or not all(ch.isalnum() or ch in "._-" for ch in name): raise ValueError("Username: letters, numbers, . _ - only.")
        if role not in ROLES: raise ValueError("Unknown role.")
        if len(pw) < 5 and not must_change: raise ValueError("Password must be at least 5 characters.")
        if self.all("SELECT 1 FROM users WHERE username=?", (name,)): raise ValueError("User already exists.")
        salt = secrets.token_hex(16)
        self.q("INSERT INTO users VALUES(?,?,?,?,?)", (name, salt, self._hash(pw, salt), role, int(must_change)))
    def verify(self, name, pw):
        r = self.all("SELECT * FROM users WHERE username=?", (name,))
        if not r: self._hash(pw, "00" * 16); return None                # same work either way
        u = r[0]
        return dict(user=u["username"], role=u["role"], must_change=bool(u["must_change"])) if hmac.compare_digest(self._hash(pw, u["salt"]), u["hash"]) else None
    def set_password(self, name, pw):
        if len(pw) < 5: raise ValueError("Password must be at least 5 characters.")
        salt = secrets.token_hex(16); self.q("UPDATE users SET salt=?, hash=?, must_change=0 WHERE username=?", (salt, self._hash(pw, salt), name))
    def users(self): return self.all("SELECT username, role, must_change FROM users ORDER BY username")
    def delete_user(self, name):
        admins = [u for u in self.users() if u["role"] == "admin"]
        if len(admins) == 1 and admins[0]["username"] == name: raise ValueError("Cannot delete the last admin.")
        self.q("DELETE FROM users WHERE username=?", (name,))
