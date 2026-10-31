
import pickle
import numpy as np
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.lines as ml

from pathlib import Path
from matplotlib.patches import (
    FancyBboxPatch,
    FancyArrowPatch,
    Rectangle,
    Wedge
)

# ============================================================
# 1. CONFIGURATION AND PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "figs"
DATA_FILE = BASE_DIR / "out.pkl"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 7,
    "font.family": "serif",
    "axes.linewidth": 0.6,
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

# ============================================================
# 2. LOAD EXPERIMENTAL DATA
# ============================================================

if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"Missing experimental data: {DATA_FILE}\n"
        "Run sim.py first to generate out.pkl."
    )

with open(DATA_FILE, "rb") as f:
    d = pickle.load(f)

required = {"roc", "res", "cm"}

if not required.issubset(d.keys()):
    raise ValueError(
        f"out.pkl must contain these keys: {required}"
    )

roc = d["roc"]
res = d["res"]
cm = np.array(d["cm"])

models = ["cam", "or", "prop"]

for model in models:
    if model not in roc or model not in res:
        raise ValueError(f"Missing model results: {model}")

    for metric in [
        "class_recall",
        "fa_per_day",
        "interrupts_per_day"
    ]:
        if metric not in res[model]:
            raise ValueError(
                f"Missing {metric} for {model}"
            )

# Consistent colors
COLORS = {
    "cam": "#999999",
    "or": "#e8742c",
    "prop": "#1f3b66"
}

NAMES = {
    "cam": "Camera-only motion alarm",
    "or": "Multi-sensor OR rule",
    "prop": "Proposed agentic fusion"
}

print("Experimental data loaded successfully.")

# ============================================================
# FIGURE 1: PROPOSED SYSTEM ARCHITECTURE
# ============================================================

fig, ax = plt.subplots(figsize=(7.1, 2.75))

ax.set_xlim(0, 100)
ax.set_ylim(0, 40)
ax.axis("off")


def box(x, y, w, h, text, fc,
        ec="#333333", fs=6.3, bold=False):

    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.25,rounding_size=1",
        facecolor=fc,
        edgecolor=ec,
        linewidth=0.7
    )

    ax.add_patch(patch)

    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        fontweight="bold" if bold else "normal"
    )


def arr(x1, y1, x2, y2, color="#333333",
        ls="-", mutation_scale=6):

    if np.isclose(x1, x2) and np.isclose(y1, y2):
        return

    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=mutation_scale,
        linewidth=0.7,
        color=color,
        linestyle=ls
    )

    ax.add_patch(arrow)


# Layer headings
headings = [
    (1, "Sensing"),
    (21, "Perception agents"),
    (44, "Reasoning agents"),
    (68, "Decision / action")
]

for x, title in headings:
    ax.text(
        x + 8,
        38.3,
        title,
        fontsize=7,
        fontweight="bold",
        color="#1f3b66",
        ha="center"
    )


# Sensing layer
sensors = [
    "Visible camera",
    "Thermal camera",
    "Radar",
    "Fence / fiber",
    "RF / acoustic"
]

for i, sensor in enumerate(sensors):
    box(
        1,
        31 - i * 6.3,
        15,
        4.6,
        sensor,
        "#e8eef7"
    )


# Perception agents
perception = [
    "Vision agent\n(detect, track)",
    "Vehicle agent",
    "Drone agent",
    "Perimeter agent\n(fence, gate, zone)"
]

for i, agent in enumerate(perception):
    box(
        21,
        30 - i * 7.6,
        16,
        5.4,
        agent,
        "#e6f4e6"
    )


# Sensing to perception connections
perception_y = [32.7, 25.1, 17.5, 9.9]

for i in range(5):
    target_y = perception_y[min(i, 3)]

    arr(
        16.3,
        33.3 - i * 6.3,
        20.7,
        target_y,
        "#888888"
    )


# Reasoning agents
box(
    44, 24, 17, 8,
    "Fusion agent\n(multi-sensor +\ncontext)",
    "#fff2d6"
)

box(
    44, 12.5, 17, 8,
    "Behaviour agent\n(loitering, group,\ntrajectory)",
    "#fff2d6"
)

box(
    44, 1.5, 17, 8,
    "Risk agent\n(severity, proximity\n-> L/M/H/C)",
    "#fff2d6"
)


# Perception to reasoning connections
for y in [33.5, 25, 17, 9]:
    target = 28 if y > 20 else 16

    arr(
        37.3, y,
        43.7, target,
        "#888888"
    )


# Reasoning pipeline
arr(52.5, 23.8, 52.5, 20.9)
arr(52.5, 12.3, 52.5, 9.9)


# Orchestrator
box(
    68, 22, 16, 12,
    "Orchestrator\n(controller)\nplan, policy check,\nroute, log",
    "#fde0dc"
)

arr(61.3, 28, 67.7, 28)
arr(61.3, 16.5, 67.5, 24)
arr(61.3, 5.5, 67.5, 22.5)


# Alert agent
box(
    68, 8, 16, 8,
    "Alert agent\nconsole - digest\nSMS / radio",
    "#f3e3f7"
)

arr(76, 21.7, 76, 16.3)


# Human operator
box(
    88, 22, 11, 12,
    "Human\noperator\n(approve /\noverride)",
    "#ffffff",
    bold=True
)

arr(84.3, 28, 87.7, 28)


# Alert to audit log
arr(76, 7.7, 76, 5.2)

# Audit log
box(
    68, 0.8, 16, 4,
    "Audit log",
    "#eeeeee"
)


# Human feedback
arr(84.3, 12, 93.5, 21.7)

ax.text(
    91.5, 15,
    "confirm /\nrelabel",
    fontsize=5.5,
    color="#333333"
)

# Feedback arrow - corrected mutation scale
arr(
    93.5, 21.7,
    84.4, 3,
    "#333333",
    mutation_scale=5
)

# Retraining feedback
ax.annotate(
    "",
    xy=(61, 3),
    xytext=(68, 3),
    arrowprops=dict(
        arrowstyle="-|>",
        linewidth=0.7,
        linestyle="--",
        color="#c0392b"
    )
)

ax.text(
    64.5, 4.2,
    "retrain",
    fontsize=5.5,
    color="#c0392b",
    ha="center"
)

plt.savefig(
    OUTPUT_DIR / "fig1_arch.pdf",
    bbox_inches="tight"
)

plt.close(fig)

print("Figure 1 generated.")


# ============================================================
# FIGURE 2: BORDER SURVEILLANCE SCENARIO
# ============================================================

fig, ax = plt.subplots(figsize=(3.45, 3.0))

ax.set_xlim(0, 100)
ax.set_ylim(0, 90)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])

# Background
ax.add_patch(
    Rectangle(
        (0, 0), 100, 90,
        facecolor="#efe9d8",
        edgecolor="black",
        linewidth=0.6
    )
)

# Restricted zone
ax.add_patch(
    Rectangle(
        (0, 48), 100, 14,
        facecolor="#f6d9d5",
        alpha=0.7,
        edgecolor="none"
    )
)

ax.text(
    2, 58.5,
    "Restricted zone",
    fontsize=5.5,
    color="#8a2b20"
)

# Border fence
ax.plot([0, 100], [62, 62], "k-", linewidth=1.6)

ax.text(
    98, 63.5,
    "Border fence",
    fontsize=5.5,
    ha="right"
)

# Gate
ax.add_patch(
    Rectangle(
        (45, 60.5), 10, 3,
        facecolor="#888888",
        edgecolor="black",
        linewidth=0.5
    )
)

ax.text(
    50, 66,
    "Gate",
    fontsize=5.5,
    ha="center"
)

# Foreign side
ax.add_patch(
    Rectangle(
        (0, 62), 100, 28,
        facecolor="#d9e6f2",
        alpha=0.5,
        edgecolor="none"
    )
)

ax.text(
    3, 85,
    "Foreign side",
    fontsize=5.5,
    color="#335577"
)

# Camera locations
for x, name in [(15, "T1"), (50, "T2"), (85, "T3")]:

    ax.plot(
        x, 40,
        marker="s",
        markersize=5,
        color="#1f3b66"
    )

    ax.text(
        x, 34.5,
        name + "\ncam+thermal",
        fontsize=4.8,
        ha="center"
    )

    ax.add_patch(
        Wedge(
            (x, 40),
            45,
            50,
            130,
            facecolor="#1f3b66",
            alpha=0.07,
            edgecolor="#1f3b66",
            linewidth=0.4
        )
    )


# Radar
ax.plot(
    50, 20,
    "^",
    markersize=6,
    color="#2a7f2a"
)

ax.text(
    50, 13,
    "Radar",
    fontsize=5,
    ha="center"
)


# Threat risk colors
risk_colors = {
    "C": "#b00020",
    "H": "#e8742c",
    "M": "#e6b800",
    "L": "#4a9d4a"
}


def track(points, risk, label, ls="-"):

    p = np.array(points)

    ax.plot(
        p[:, 0],
        p[:, 1],
        linestyle=ls,
        color=risk_colors[risk],
        linewidth=1.2
    )

    ax.plot(
        p[-1, 0],
        p[-1, 1],
        "o",
        color=risk_colors[risk],
        markersize=4
    )

    if label:
        ax.text(
            p[-1, 0] + 1.5,
            p[-1, 1] + 1.5,
            label,
            fontsize=5.2,
            color=risk_colors[risk],
            fontweight="bold"
        )


# Illustrative trajectories
track(
    [(22, 86), (24, 76), (26, 67), (28, 58), (30, 50)],
    "C",
    ""
)

ax.text(
    4, 74,
    "Group x5 (C)",
    fontsize=5.2,
    color=risk_colors["C"],
    fontweight="bold"
)

track(
    [(70, 40), (68, 45), (66, 50), (60, 54)],
    "H",
    "Vehicle (H)"
)

track(
    [(88, 50), (92, 55), (94, 57)],
    "M",
    "Loiter (M)"
)

track(
    [(8, 45), (10, 48), (11, 50)],
    "L",
    "",
    ":"
)

ax.text(
    2, 41.5,
    "Animal (L)",
    fontsize=5.2,
    color=risk_colors["L"],
    fontweight="bold"
)

# Drone marker
ax.plot(
    76, 78,
    "x",
    color=risk_colors["H"],
    markersize=6,
    markeredgewidth=1.5
)

ax.text(
    78, 79.5,
    "Drone (H)",
    fontsize=5.2,
    color=risk_colors["H"],
    fontweight="bold"
)

# Abandoned object marker
ax.plot(
    40, 53,
    "D",
    color=risk_colors["C"],
    markersize=4
)

ax.text(
    43, 52,
    "Abandoned obj. (C)",
    fontsize=5.2,
    color=risk_colors["C"],
    fontweight="bold"
)

# Legend
handles = [
    ml.Line2D([], [], color=risk_colors[k], linewidth=2)
    for k in "CHML"
]

ax.legend(
    handles,
    ["Critical", "High", "Medium", "Low"],
    loc="lower right",
    fontsize=5,
    frameon=True,
    ncol=2,
    handlelength=1.2
)

plt.savefig(
    OUTPUT_DIR / "fig2_scene.pdf",
    bbox_inches="tight"
)

plt.close(fig)

print("Figure 2 generated.")


# ============================================================
# FIGURE 3: ROC CURVE AND CLASS RECALL
# ============================================================

fig, axs = plt.subplots(
    1, 2,
    figsize=(7.1, 2.5)
)

# ROC curve
ax = axs[0]

for model in models:

    fpr, tpr, auc_value = roc[model]

    ax.plot(
        fpr,
        tpr,
        color=COLORS[model],
        linewidth=1.3,
        label=f"{NAMES[model]} (AUC={auc_value:.3f})"
    )

ax.plot(
    [0, 1],
    [0, 1],
    "k:",
    linewidth=0.5
)

ax.set_xlabel("False positive rate")
ax.set_ylabel("True positive rate")

ax.legend(
    fontsize=5.8,
    loc="lower right"
)

ax.grid(alpha=0.25)

ax.set_title(
    "(a) ROC, threat vs. non-threat",
    fontsize=7
)


# Per-class recall
ax = axs[1]

classes = [
    "Person",
    "Group",
    "Loiter",
    "Vehicle",
    "Drone",
    "Abandoned",
    "Fence\nbreach"
]

x = np.arange(len(classes))
width = 0.27

for i, model in enumerate(models):

    recall = np.asarray(
        res[model]["class_recall"],
        dtype=float
    )

    if len(recall) != len(classes):
        raise ValueError(
            f"{model} must contain 7 class recall values."
        )

    ax.bar(
        x + (i - 1) * width,
        recall,
        width,
        color=COLORS[model],
        label=NAMES[model]
    )

ax.set_xticks(x)
ax.set_xticklabels(classes, fontsize=6)

ax.set_ylabel("Recall")
ax.set_ylim(0, 1.12)

ax.grid(
    axis="y",
    alpha=0.25
)

ax.set_title(
    "(b) Per-threat-class recall at operating point",
    fontsize=7
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "fig3_roc.pdf",
    bbox_inches="tight"
)

plt.close(fig)

print("Figure 3 generated.")


# ============================================================
# FIGURE 4: OPERATIONAL PERFORMANCE
# ============================================================

fig, axs = plt.subplots(
    1, 3,
    figsize=(7.1, 2.3),
    gridspec_kw={
        "width_ratios": [1, 1, 0.9]
    }
)

labels = [
    "Camera\nonly",
    "Multi-\nsensor OR",
    "Proposed"
]


# False alarms
ax = axs[0]

false_alarms = [
    res[k]["fa_per_day"]
    for k in models
]

ax.bar(
    range(3),
    false_alarms,
    color=[COLORS[k] for k in models]
)

for i, value in enumerate(false_alarms):

    ax.text(
        i,
        value + 0.6,
        f"{value:.1f}",
        ha="center",
        fontsize=6
    )

ax.set_xticks(range(3))
ax.set_xticklabels(labels, fontsize=6)

ax.set_ylabel("False alarms per day")

ax.set_title(
    "(a) False alarms",
    fontsize=7
)

ax.grid(
    axis="y",
    alpha=0.25
)


# Operator workload
ax = axs[1]

interruptions = [
    res[k]["interrupts_per_day"]
    for k in models
]

ax.bar(
    range(3),
    interruptions,
    color=[COLORS[k] for k in models]
)

for i, value in enumerate(interruptions):

    ax.text(
        i,
        value + 0.8,
        f"{value:.1f}",
        ha="center",
        fontsize=6
    )

ax.set_xticks(range(3))
ax.set_xticklabels(labels, fontsize=6)

ax.set_ylabel("Operator interruptions per day")

ax.set_title(
    "(b) Operator workload",
    fontsize=7
)

ax.grid(
    axis="y",
    alpha=0.25
)


# Risk-level confusion matrix
ax = axs[2]

if cm.shape != (4, 4):
    raise ValueError(
        f"Expected a 4x4 confusion matrix, got {cm.shape}"
    )

ax.imshow(cm, cmap="Blues")

risk_labels = ["L", "M", "H", "C"]

ax.set_xticks(range(4))
ax.set_xticklabels(risk_labels)

ax.set_yticks(range(4))
ax.set_yticklabels(risk_labels)

ax.set_xlabel("Predicted risk")
ax.set_ylabel("True risk")

for i in range(4):

    for j in range(4):

        value = cm[i, j]

        text_color = (
            "white"
            if value > cm.max() / 2
            else "black"
        )

        ax.text(
            j,
            i,
            str(value),
            ha="center",
            va="center",
            fontsize=6,
            color=text_color
        )

ax.set_title(
    "(c) Risk-level confusion",
    fontsize=7
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "fig4_ops.pdf",
    bbox_inches="tight"
)

plt.close(fig)

print("Figure 4 generated.")


# ============================================================
# 5. FINAL OUTPUT
# ============================================================

print("\n" + "=" * 50)
print("ALL FIGURES GENERATED SUCCESSFULLY")
print("=" * 50)

for file in sorted(OUTPUT_DIR.glob("*.pdf")):

    print(
        f"{file.name} | {file.stat().st_size / 1024:.2f} KB"
    )

print("\nOutput directory:")
print(OUTPUT_DIR)
