# Border Watch: AI-Based Intelligent Border Surveillance (v3)

Multi-camera dashboard with **manual video upload**, neural-network detection, restricted zones you draw, risk levels, real-time alerts
with replay clips, a multi-agent control layer, and role-based login. Companion to the IEEE paper in `docs/`.

## Run it
**Easiest:** double-click `run.bat` (Windows) or run `./run.sh` (macOS/Linux). It installs what it needs and starts the console.

**Manual:**
```
pip install -r requirements.txt
python run_gui.py
```
Open http://localhost:8000. First sign-in: **admin / admin**, then change the password (a banner reminds you).
Docker: `docker compose up --build`.

## Use it
1. **Upload a video:** click *Upload video* on a camera tile (or drag a file onto it). Boxes with labels and confidence appear on the feed.
2. **Draw restricted zones:** Live Cameras > *Draw restricted zones* > click the corners on the picture > *Finish shape* > *Save zones*. Without zones, everything below the *default fence line* slider is restricted.
3. **Events:** each detection gets a risk level and an evidence frame plus a **replay clip** (4 s before, 3 s after, scrubbable). Acknowledge, Dispatch or Dismiss; High and Critical must be acknowledged first.
4. **Assistant:** ask "show high risk events", "explain #1001", "summarize suspicious activity".
5. **Analytics:** risk and type charts, 30-minute timeline, camera health, per-camera activity heatmaps. **Reports:** CSV and a printable report with evidence images.
6. **Settings:** movement trails, heatmap overlay, low-light enhancement, alarm sound, webhook, users and passwords.
No video? Use `sample_videos/synthetic_border.mp4` with `--backend motion`, or turn on *Demo data*.

## Advanced features
| Feature | Details |
|---|---|
| Neural detector | YOLOX-Tiny (bundled, run by OpenCV). Falls back to a motion+HOG heuristic if the model cannot load. |
| Zones | Draw polygons per camera; foot-point tests; crossing, vehicle intrusion, loitering near zone, fence tampering. |
| Tracking | Constant-velocity prediction so fast vehicles keep their ID. |
| Replay clips | Pre/post-event frames saved per event and scrubbed in the browser. |
| Heatmap and trails | Where people and vehicles were seen; optional overlay on the feed. |
| Low light | Automatic contrast enhancement before detection when the frame is dark. |
| Login and roles | admin (everything), operator (acknowledge, dispatch, upload, zones), viewer (read only). PBKDF2-hashed passwords, login rate limit, session cookie. |
| Persistence | SQLite (`data/borderwatch.db`): events, users, settings, audit log survive restarts. |
| Webhook | JSON POST for events at or above a level you choose. |
| Alarm sound | Browser beep on new High or Critical events. |

## Agents and control
Vision, Behaviour, Perimeter, Vehicle, Drone, Fusion, Risk, Alert and the Orchestrator. The orchestrator is the only route between agents,
enforces a tool allow-list, requires acknowledgement before High/Critical dispatch, escalates unacknowledged Critical alerts after 25 s, logs every
action with the user name, and falls back to raw alarms if an agent fails. Risk = severity x (1 + 0.3 group of 4+, + 0.4 inside a zone, + 0.2 low light).

## Honest limits
- The bundled detector is a general COCO model. It finds people and vehicles; it was checked on a real photograph and a clip with a real person, **not on border footage**. Test on your own videos before relying on it.
- COCO has **no drone class**. Birds, kites and aircraft stand in, so expect false or missed drone alerts. Use a drone-trained model (`models/README.md`).
- The optional Ultralytics backend (`--backend yolo`) is included but was **not run** in the build environment.
- Zone logic assumes a fixed camera. Moving or panning cameras need new zones.
- The map is stylised, not GPS. *Demo data* is simulated.
- Login is basic: sessions are held in memory, traffic is plain HTTP, and the default is local-only. Do not expose it to the internet without HTTPS and a hardened setup.
- Run script, Docker files and webhook were tested only partly (webhook against a local receiver; `run.bat` and Docker not run).
- Detections are aids. A trained person must verify them. Review privacy, bias and legal rules before real use.

## Commands
```
python run_gui.py --help                 # port, host, backend, model, --no-login
python run_demo.py                       # headless comparison: raw alarms vs. agents
python -m unittest discover -s tests     # 22 tests (also passing on OpenCV 5.0)
python tools/make_test_video.py          # regenerate the synthetic clip
```

## Layout
```
run.bat run.sh run_gui.py run_demo.py Dockerfile docker-compose.yml requirements.txt
border_watch/  config.py db.py store.py engine.py server.py simulator.py events.py
  agents/ (simulated-sensor agents + orchestrator)   video/ detector.py tracker.py pipeline.py
web/ index.html app.js style.css (+ standalone_console.html, a browser-only simulation)
models/  tests/  tools/  sample_videos/  paper_simulation/  docs/
```
Data (database, uploads, evidence, clips) is stored in `data/`.
