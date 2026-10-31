"""Central configuration: classes, sensor model, geometry, risk and policy settings."""
CLASSES = ["person", "group", "loiter", "vehicle", "drone", "abandoned", "breach",
           "animal", "vegetation", "patrol"]
NAMES = ["Person crossing", "Group movement", "Loitering", "Vehicle intrusion", "Drone",
         "Abandoned object", "Fence breach", "Animal", "Wind-blown vegetation", "Authorised patrol"]
N_THREAT = 7                      # classes 0..6 are threats, 7..9 are benign
SENSORS = ["cam", "thermal", "radar", "fence", "rf"]
# Mean sensor response per class (rows) and sensor (columns). Assumed values.
MEANS = [[.75, .80, .60, .20, 0], [.80, .85, .70, .25, 0], [.70, .75, .50, .30, 0],
         [.80, .70, .85, .10, 0], [.35, .40, .55, 0, .85], [.55, .60, .10, 0, 0],
         [.50, .55, .30, .90, 0], [.45, .60, .50, .25, 0], [.50, .05, .40, .30, 0],
         [.80, .80, .70, .15, 0]]
SEVERITY = [.5, .8, .3, .8, .6, .9, .7]
SPEED = [(14, 6), (12, 5), (2, 2), (50, 15), (40, 12), (0, .8), (0, .8), (22, 12), (0, 1), (45, 12)]
PRIOR = [1.6, .7, 1.0, .8, .5, .5, .9, 25, 20, 8]   # events per day (relative frequency)
W, H, FENCE_Y = 900, 560, 250
TOWERS = [(150, 380), (450, 380), (750, 380)]
RADAR = (450, 520)
LEVELS = ["Low", "Medium", "High", "Critical"]
RISK_CUTS = (0.45, 0.70, 1.00)
POLICY = dict(tau=0.60, min_obs=4, strong_threat=0.80, escalate_after=25.0)
CHANNELS = {0: ["digest"], 1: ["console"], 2: ["console", "audio"],
            3: ["console", "audio", "radio", "commander if unacknowledged"]}
ACTIONS = ["Log and review in digest.", "Send patrol to observe and keep tracking.",
           "Dispatch patrol to the fence line and cue the thermal camera.",
           "Dispatch quick-reaction team to the gate and block the access road.",
           "Check for counter-drone cover and alert the air-defence desk.",
           "Cordon the area and request a specialist. Do not approach.",
           "Send a team to inspect the fence section and check camera cover."]
# Which tools each agent may call. Anything else is blocked and logged.
TOOL_ALLOWLIST = {
    "vision": {"read_cam", "read_thermal", "cue_camera"},
    "vehicle": {"read_radar"}, "drone": {"read_radar", "read_rf"},
    "perimeter": {"read_fence", "read_gate_state"},
    "behaviour": {"read_tracks"}, "fusion": {"read_context"}, "risk": set(),
    "alert": {"send_console", "send_audio", "send_radio"},
    "orchestrator": {"dispatch_response", "launch_inspection_drone"}}
NEEDS_HUMAN_APPROVAL = {"dispatch_response", "launch_inspection_drone"}

def sensor_mean(cls, k, night=False, bad=False):
    """Expected response of sensor k to class cls, adjusted for night and weather."""
    m = MEANS[cls][k]
    if k == 0:
        m *= (0.45 if night else 1) * (0.75 if bad else 1)
    if k == 1 and bad:
        m *= 0.9
    return m
