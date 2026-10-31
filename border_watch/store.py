"""Event store, statistics and the offline AI Security Agent (rule-based assistant)."""
import csv, io, json, time, datetime as dt
from collections import Counter
from . import config as C

LEVELS = C.LEVELS
STATUS_NAMES = {"new": "New", "ack": "Acknowledged", "done": "Dispatched", "dismissed": "Dismissed", "logged": "Logged",
                "expired": "Expired", "withdrawn": "Withdrawn"}
CAMS = [("CAM-01", "North Sector"), ("CAM-02", "East Sector"), ("CAM-03", "River Zone"),
        ("CAM-04", "Mountain Sector"), ("CAM-05", "Boundary Gate")]

class EventStore:
    def __init__(self, db=None, start_id=1001):
        self.db, self.events, self.next_id = db, [], start_id
        if db:
            self.events = [json.loads(r["data"]) for r in db.all("SELECT data FROM events ORDER BY id")]
            if self.events: self.next_id = max(e["id"] for e in self.events) + 1
    def add(self, **kw):
        ev = dict(id=self.next_id, ts=time.time(), status="new", src="video", ref=None, snap=False, esc=False, channels=[], clip=0, by=None)
        ev.update(kw)
        self.next_id += 1; self.events.append(ev); self.save(ev); return ev
    def save(self, ev):
        if self.db: self.db.q("INSERT OR REPLACE INTO events(id,data) VALUES(?,?)", (ev["id"], json.dumps(ev)))
    def clear(self):
        self.events.clear()
        if self.db: self.db.q("DELETE FROM events")
    def get(self, eid):
        return next((e for e in self.events if e["id"] == eid), None)
    def counts_by_level(self):
        c = Counter(e["level"] for e in self.events); return [c.get(i, 0) for i in range(4)]
    def counts_by_type(self):
        return dict(Counter(e["type"] for e in self.events))
    def timeline(self, minutes=30):
        now = time.time(); b = [0] * minutes
        for e in self.events:
            m = int((now - e["ts"]) // 60)
            if 0 <= m < minutes: b[minutes - 1 - m] += 1
        return b
    def csv(self):
        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["ID", "Time", "Camera", "Sector", "Event type", "Objects", "Risk level", "Risk score", "Confidence", "Status", "Source"])
        for e in self.events:
            w.writerow([e["id"], dt.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M:%S"), e["cam"], e["sector"], e["type"],
                        e["objects"], LEVELS[e["level"]], e.get("risk", ""), e["conf"], STATUS_NAMES.get(e["status"], e["status"]), e["src"]])
        return out.getvalue()
    def report_html(self, kpi, thumbs=None, cams=None):
        lv = self.counts_by_level(); ty = self.counts_by_type()
        rows = "".join(f"<tr><td>#{e['id']}</td><td>{dt.datetime.fromtimestamp(e['ts']).strftime('%H:%M:%S')}</td><td>{e['cam']} {e['sector']}</td>"
                       f"<td>{e['type']}</td><td>{e['objects']}</td><td>{LEVELS[e['level']]}</td><td>{e['conf']:.2f}</td><td>{STATUS_NAMES.get(e['status'], e['status'])}</td></tr>"
                       for e in reversed(self.events[-200:]))
        return f"""<!doctype html><meta charset=utf-8><title>Border Watch report</title><style>body{{font:14px Arial;margin:30px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:5px 8px;text-align:left}}th{{background:#eee}}h1{{margin:0}}</style>
<h1>Border Watch: Incident Report</h1><p>Generated {dt.datetime.now():%Y-%m-%d %H:%M:%S}. Events from uploaded video and simulated demo data.</p>
<h3>Summary</h3><p>Total events: <b>{len(self.events)}</b>. Critical {lv[3]}, High {lv[2]}, Medium {lv[1]}, Low {lv[0]}.
Handled threats: {kpi.get('handled', 0)}. Policy blocks: {kpi.get('blocked', 0)}.</p>
<p>By type: {', '.join(f'{k} {v}' for k, v in sorted(ty.items(), key=lambda x: -x[1])) or 'none'}</p>
{"".join(f'<div style="display:inline-block;margin:4px;font-size:12px"><img src="data:image/jpeg;base64,{b}" width=260><br>#{i} {self.get(i)["type"]} ({LEVELS[self.get(i)["level"]]})</div>' for i, b in (thumbs or {}).items())}
<h3>Per camera</h3><p>{', '.join(f"{c}: {n} events" for c, n in sorted(Counter(e['cam'] for e in self.events).items())) or 'none'}</p>
<h3>Events</h3><table><tr><th>ID<th>Time<th>Camera<th>Type<th>Objects<th>Risk<th>Confidence<th>Status</tr>{rows}</table>
<p style="color:#777">Detections are automated and must be verified by a human operator.</p>"""

def _line(e):
    return f"#{e['id']} {dt.datetime.fromtimestamp(e['ts']):%H:%M:%S} {e['cam']} {e['type']} ({e['objects']}), {LEVELS[e['level']]} risk, {e['conf']:.2f}, {STATUS_NAMES.get(e['status'], e['status'])}"

def answer(q, store, kpi, cams_online, backend):
    """Offline rule-based assistant: answers questions about the detected events."""
    ql, ev = q.lower().strip(), store.events
    import re
    m = re.search(r"#?(\d{4})", ql)
    if m and store.get(int(m.group(1))):
        e = store.get(int(m.group(1)))
        why = {"Unauthorized Crossing": "a person crossed the fence line into the restricted zone",
               "Group Movement": "three or more people moved together", "Vehicle Intrusion": "a vehicle entered the restricted zone",
               "Drone Detection": "an aerial object was tracked for more than a second", "Loitering": "a person stayed near the fence for a long time",
               "Fence Breach": "a person lingered on the fence line (possible climbing or cutting)", "Abandoned Object": "an object stayed still for a long time"}.get(e["type"], e["type"])
        return (f"Event #{e['id']}: {e['type']} on {e['cam']} ({e['sector']}). Reason: {why}. Risk level {LEVELS[e['level']]} (score {e.get('risk', 'n/a')}). "
                f"Confidence {e['conf']:.2f}. Status: {STATUS_NAMES.get(e['status'], e['status'])}. "
                + ("Policy: acknowledge before dispatching a response." if e["level"] >= 2 else "No approval step needed."))
    if not ev and not any(k in ql for k in ("help", "risk level", "camera", "explain")):
        return "No events have been detected yet. Upload a video to a camera tile, or turn on demo data in Settings."
    if any(k in ql for k in ("risk level", "explain risk", "how is risk", "what is risk")):
        return ("Risk = event severity x (1 + 0.3 if a group of 4 or more, + 0.4 if inside the restricted zone, + 0.2 in low light). "
                "Low is below 0.45, Medium below 0.70, High below 1.00, Critical above. High and Critical alerts must be acknowledged by an operator before any response is dispatched.")
    if "report" in ql:
        return "The report is ready on the Reports page. Use Download CSV for a spreadsheet, or Open printable report for a summary you can save as PDF."
    if "camera" in ql:
        return f"{cams_online} of 5 cameras are online. Detection backend: {backend}."
    lv = store.counts_by_level(); ty = store.counts_by_type()
    typemap = {"drone": "Drone Detection", "vehicle": "Vehicle Intrusion", "crossing": "Unauthorized Crossing", "loiter": "Loitering",
               "fence": "Fence Breach", "group": "Group Movement", "abandon": "Abandoned Object"}
    for k, v in typemap.items():
        if k in ql:
            sel = [e for e in ev if e["type"] == v]
            return f"{len(sel)} {v} event(s)." + ("" if not sel else " Latest: " + _line(sel[-1]))
    if any(k in ql for k in ("high", "critical", "serious", "priority", "urgent", "dangerous")):
        sel = [e for e in ev if e["level"] >= 2 and e["status"] in ("new", "ack")]
        return (f"{len(sel)} open high-risk event(s)." + ("" if not sel else "\n" + "\n".join(_line(e) for e in sel[-5:][::-1])))
    if any(k in ql for k in ("last", "latest", "recent", "new")):
        return "Most recent events:\n" + "\n".join(_line(e) for e in ev[-5:][::-1])
    if any(k in ql for k in ("how many", "count", "total")):
        return f"{len(ev)} events in total: Critical {lv[3]}, High {lv[2]}, Medium {lv[1]}, Low {lv[0]}."
    if any(k in ql for k in ("summar", "suspicious", "happen", "overview", "status")):
        top = ", ".join(f"{k} {v}" for k, v in sorted(ty.items(), key=lambda x: -x[1])[:4])
        hi = sum(1 for e in ev if e["level"] >= 2 and e["status"] in ("new", "ack"))
        return (f"{len(ev)} events so far ({top}). {hi} high-risk event(s) still need attention. "
                f"Handled {kpi.get('handled', 0)}, missed {kpi.get('missed', 0)}. Latest: {_line(ev[-1])}")
    return ("I can analyse detected events, explain risk levels, summarise suspicious activity, generate reports and answer questions such as "
            "'show high risk events', 'any drones?', 'explain #1042' or 'how many events?'.")
