from pathlib import Path
import argparse
import json
import pickle
import heapq

import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_curve,
    auc,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.model_selection import cross_val_predict


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(
    description="Border Surveillance research simulation"
)

parser.add_argument("--seed", type=int, default=7)
parser.add_argument("--days", type=int, default=60)
parser.add_argument("--train-days", type=int, default=30)

args = parser.parse_args()

SEED = args.seed
DAYS = args.days
TRAIN_DAYS = args.train_days

if DAYS <= TRAIN_DAYS or TRAIN_DAYS < 5:
    raise ValueError("DAYS must be greater than TRAIN_DAYS, and TRAIN_DAYS must be at least 5.")

rng = np.random.default_rng(SEED)

# First seven classes are treated as threats.
CLASSES = [
    "person",
    "group",
    "loiter",
    "vehicle",
    "drone",
    "abandoned",
    "breach",
    "animal",
    "vegetation",
    "patrol",
    "weather",
]

NUM_THREATS = 7
NUM_CLASSES = len(CLASSES)

# Expected event rates per day.
RATE = np.array([
    1.6, 0.7, 1.0, 0.8, 0.5, 0.5, 0.9,
    25, 20, 8, 12
])

# Sensor detection characteristics:
# Camera, thermal, radar, fence, RF.
SENSOR_MATRIX = np.array([
    [.75, .80, .60, .20, 0],
    [.80, .85, .70, .25, 0],
    [.70, .75, .50, .30, 0],
    [.80, .70, .85, .10, 0],
    [.35, .40, .55, 0, .85],
    [.55, .60, .10, 0, 0],
    [.50, .55, .30, .90, 0],
    [.45, .60, .50, .25, 0],
    [.50, .05, .40, .30, 0],
    [.80, .80, .70, .15, 0],
    [.40, .05, .35, .35, 0],
])

SEVERITY = np.array([
    .5, .8, .3, .8, .6, .9, .7
])

MODEL_PARAMS = {
    "max_iter": 150,
    "learning_rate": 0.08,
    "random_state": SEED,
}


# ============================================================
# 2. SYNTHETIC DATA GENERATION
# ============================================================

def generate_dataset():

    features = []
    labels = []
    day_ids = []
    timestamps = []

    speed_params = {
        0: (1.4, .5),
        1: (1.2, .4),
        2: (.2, .15),
        3: (8, 3),
        4: (6, 2),
        5: (.02, .02),
        6: (.8, .5),
        7: (2.5, 1.5),
        8: (.3, .3),
        9: (5, 3.5),
        10: (.3, .3),
    }

    dwell_params = {
        0: (40, 20),
        1: (60, 25),
        2: (600, 250),
        3: (20, 10),
        4: (120, 60),
        5: (3000, 1000),
        6: (90, 40),
        7: (60, 50),
        8: (10, 10),
        9: (60, 40),
        10: (10, 10),
    }

    for day in range(DAYS):

        for class_id in range(NUM_CLASSES):

            number_of_events = rng.poisson(RATE[class_id])

            for _ in range(number_of_events):

                is_night = rng.random() < (
                    0.6 if class_id < NUM_THREATS else 0.4
                )

                if is_night:
                    hour = rng.uniform(19, 30) % 24
                else:
                    hour = rng.uniform(6, 19)

                is_bad_weather = (
                    True if class_id == 10
                    else rng.random() < 0.2
                )

                sensor_values = SENSOR_MATRIX[class_id].copy()

                noise = np.full(5, .15)

                if is_night:
                    sensor_values[0] *= .45
                    noise[0] = .22

                if is_bad_weather:
                    sensor_values[0] *= .75
                    sensor_values[1] *= .9

                if class_id == 10 and is_bad_weather:
                    sensor_values[2] += .15

                sensor_readings = np.clip(
                    sensor_values + rng.normal(0, noise),
                    0,
                    1
                )

                if sensor_values[4] > 0:
                    sensor_readings[4] = np.clip(
                        sensor_values[4] + rng.normal(0, .1),
                        0,
                        1
                    )
                else:
                    sensor_readings[4] = abs(
                        rng.normal(0, .05)
                    )

                speed = abs(
                    rng.normal(*speed_params[class_id])
                )

                dwell = abs(
                    rng.normal(*dwell_params[class_id])
                )

                group_size = {
                    1: rng.integers(3, 9),
                    2: rng.integers(1, 4),
                    3: rng.integers(1, 3),
                    7: rng.integers(1, 5),
                }.get(class_id, 1)

                if class_id in (0, 1, 3):
                    heading = rng.normal(.6, .3)
                else:
                    heading = rng.normal(
                        0,
                        .5 if class_id in (2, 7, 9) else .3
                    )

                if class_id < NUM_THREATS:
                    distance = min(
                        rng.exponential(120),
                        600
                    )
                else:
                    distance = rng.uniform(0, 800)

                authorized = float(
                    rng.random() < (
                        .85 if class_id == 9
                        else .02 if class_id < NUM_THREATS
                        else 0
                    )
                )

                feature_row = (
                    list(sensor_readings)
                    + [
                        speed,
                        dwell,
                        group_size,
                        np.clip(heading, -1, 1),
                        distance,
                        float(is_night),
                        float(is_bad_weather),
                        authorized,
                    ]
                )

                features.append(feature_row)
                labels.append(class_id)
                day_ids.append(day)

                minute = rng.uniform(0, 60)
                timestamps.append(
                    day * 1440 + hour * 60 + minute
                )

    return (
        np.asarray(features, dtype=float),
        np.asarray(labels, dtype=int),
        np.asarray(day_ids, dtype=int),
        np.asarray(timestamps, dtype=float),
    )


# ============================================================
# 3. GENERATE AND SPLIT DATA
# ============================================================

print("\nGenerating synthetic surveillance dataset...")

X, y, day_ids, timestamps = generate_dataset()

train_mask = day_ids < TRAIN_DAYS
test_mask = ~train_mask

X_train = X[train_mask]
y_train = y[train_mask]

X_test = X[test_mask]
y_test = y[test_mask]

test_timestamps = timestamps[test_mask]

y_true_threat = (
    y_test < NUM_THREATS
).astype(int)

TEST_DAYS = DAYS - TRAIN_DAYS

print("Total samples:", len(X))
print("Training samples:", len(X_train))
print("Testing samples:", len(X_test))
print("Threat test samples:", int(y_true_threat.sum()))
print("Benign test samples:", int((1 - y_true_threat).sum()))


# ============================================================
# 4. TRAIN CLASSIFICATION MODEL
# ============================================================

print("\nTraining HistGradientBoostingClassifier...")

model = HistGradientBoostingClassifier(
    **MODEL_PARAMS
)

model.fit(X_train, y_train)

probabilities = model.predict_proba(X_test)

# Threat probability = sum of first seven class probabilities.
score_proposed = probabilities[:, :NUM_THREATS].sum(axis=1)

# Camera-only baseline.
score_camera = X_test[:, 0]

# Sensor OR baseline.
score_or = X_test[:, :5].max(axis=1)


# ============================================================
# 5. THRESHOLD TUNING USING TRAINING DATA ONLY
# ============================================================

print("\nTuning proposed-model threshold using training CV...")

cv_model = HistGradientBoostingClassifier(
    **MODEL_PARAMS
)

cv_probabilities = cross_val_predict(
    cv_model,
    X_train,
    y_train,
    cv=5,
    method="predict_proba",
)

cv_threat_score = cv_probabilities[:, :NUM_THREATS].sum(axis=1)

cv_true_threat = (
    y_train < NUM_THREATS
).astype(int)

cv_fpr, cv_tpr, cv_thresholds = roc_curve(
    cv_true_threat,
    cv_threat_score
)

valid_threshold_indices = np.where(cv_tpr >= 0.92)[0]

if len(valid_threshold_indices) == 0:
    raise RuntimeError(
        "No threshold achieved the required training-CV recall."
    )

# First qualifying threshold gives the highest threshold
# among the thresholds meeting the recall constraint.
proposed_threshold = float(
    cv_thresholds[valid_threshold_indices[0]]
)

THRESHOLDS = {
    "cam": 0.5,
    "or": 0.6,
    "prop": proposed_threshold,
}

print("Proposed threshold:", proposed_threshold)


# ============================================================
# 6. BASELINE ALERT GENERATION
# ============================================================

scores = {
    "cam": score_camera,
    "or": score_or,
    "prop": score_proposed,
}

alerts = {
    name: scores[name] > THRESHOLDS[name]
    for name in scores
}


# ============================================================
# 7. PERFORMANCE METRICS
# ============================================================

results = {
    "seed": SEED,
    "days": TEST_DAYS,
    "n_threat_test": int(y_true_threat.sum()),
    "n_benign_test": int((1 - y_true_threat).sum()),
    "n_test_samples": int(len(y_test)),
    "thresholds": THRESHOLDS,
}

roc_results = {}

for name, score in scores.items():

    fpr, tpr, _ = roc_curve(
        y_true_threat,
        score
    )

    model_auc = auc(fpr, tpr)

    roc_results[name] = (
        fpr,
        tpr,
        float(model_auc)
    )

    predicted = alerts[name]

    precision = precision_score(
        y_true_threat,
        predicted,
        zero_division=0
    )

    recall = recall_score(
        y_true_threat,
        predicted,
        zero_division=0
    )

    f1 = f1_score(
        y_true_threat,
        predicted,
        zero_division=0
    )

    true_positive = int(
        (predicted & (y_true_threat == 1)).sum()
    )

    false_positive = int(
        (predicted & (y_true_threat == 0)).sum()
    )

    class_recall = []

    for class_id in range(NUM_THREATS):

        class_mask = y_test == class_id
        denominator = int(class_mask.sum())

        if denominator == 0:
            class_recall.append(None)
        else:
            class_recall.append(
                float(
                    (predicted & class_mask).sum()
                    / denominator
                )
            )

    results[name] = {
        "auc": float(model_auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "fa_per_day": float(
            false_positive / TEST_DAYS
        ),
        "alarms_per_day": float(
            predicted.sum() / TEST_DAYS
        ),
        "class_recall": class_recall,
    }


# ============================================================
# 8. RISK CLASSIFICATION
# ============================================================

# Feature indexes:
# 0-4 = sensor readings
# 5 = speed
# 6 = dwell time
# 7 = group size
# 8 = heading
# 9 = distance
# 10 = night
# 11 = bad weather
# 12 = authorization

group_size = X_test[:, 7]
distance = X_test[:, 9]
night = X_test[:, 10]

risk_modifier = (
    1
    + .3 * (group_size >= 4)
    + .4 * (distance < 100)
    + .2 * night
)


def risk_level(risk_score):
    return np.digitize(
        risk_score,
        [.45, .7, 1.0]
    )


true_risk = np.where(
    y_test < NUM_THREATS,
    SEVERITY[np.minimum(y_test, NUM_THREATS - 1)]
    * risk_modifier,
    0
)

threat_probabilities = probabilities[:, :NUM_THREATS]

estimated_risk = (
    (threat_probabilities * SEVERITY).sum(axis=1)
    / np.maximum(threat_probabilities.sum(axis=1), 1e-9)
    * risk_modifier
)

true_levels = risk_level(true_risk)
predicted_levels = risk_level(estimated_risk)

# Evaluate risk classification on proposed-model alerts
# that are actually threats.
risk_evaluation_mask = (
    alerts["prop"] & (y_true_threat == 1)
)

if risk_evaluation_mask.any():

    risk_cm = confusion_matrix(
        true_levels[risk_evaluation_mask],
        predicted_levels[risk_evaluation_mask],
        labels=[0, 1, 2, 3]
    )

    risk_accuracy = accuracy_score(
        true_levels[risk_evaluation_mask],
        predicted_levels[risk_evaluation_mask]
    )

    risk_within_one = np.mean(
        np.abs(
            true_levels[risk_evaluation_mask]
            - predicted_levels[risk_evaluation_mask]
        ) <= 1
    )

else:

    risk_cm = np.zeros((4, 4), dtype=int)
    risk_accuracy = float("nan")
    risk_within_one = float("nan")


results["risk_acc"] = float(risk_accuracy)
results["risk_within1"] = float(risk_within_one)
results["risk_cm"] = risk_cm.tolist()


# ============================================================
# 9. OPERATOR QUEUE SIMULATION
# ============================================================

def simulate_queue(
    arrival_times,
    priorities,
    priority_enabled,
    seed
):
    """
    Simulates a single operator processing alerts.

    Returns waiting time for each alert.
    """

    local_rng = np.random.default_rng(seed)

    order = np.argsort(arrival_times)

    service_times = local_rng.exponential(
        5.0,
        len(arrival_times)
    )

    current_time = 0.0
    index = 0
    total = len(arrival_times)

    waiting_times = {}

    priority_queue = []

    while index < total or priority_queue:

        if (
            not priority_queue
            and index < total
            and arrival_times[order[index]] > current_time
        ):
            current_time = arrival_times[order[index]]

        while (
            index < total
            and arrival_times[order[index]] <= current_time
        ):
            event_index = order[index]

            if priority_enabled:
                priority_key = -priorities[event_index]
            else:
                priority_key = arrival_times[event_index]

            heapq.heappush(
                priority_queue,
                (
                    priority_key,
                    arrival_times[event_index],
                    event_index,
                )
            )

            index += 1

        _, _, event_index = heapq.heappop(
            priority_queue
        )

        waiting_times[event_index] = (
            current_time - arrival_times[event_index]
        )

        current_time += service_times[event_index]

    return waiting_times


# High-risk ground-truth events.
high_risk = (
    (true_levels >= 2)
    & (y_true_threat == 1)
)


def calculate_queue_statistics(
    alert_mask,
    priorities,
    priority_enabled,
    seed=3
):

    selected_indices = np.where(alert_mask)[0]

    if len(selected_indices) == 0:
        return (
            float("nan"),
            float("nan"),
            0.0
        )

    selected_times = test_timestamps[selected_indices]

    selected_priorities = priorities[selected_indices]

    waiting_times = simulate_queue(
        selected_times,
        selected_priorities,
        priority_enabled,
        seed
    )

    waits = np.array([
        waiting_times[i]
        for i in range(len(selected_indices))
    ])

    selected_high_risk = high_risk[selected_indices]

    if selected_high_risk.any():

        high_waits = waits[selected_high_risk]

        mean_wait = float(high_waits.mean())

        acknowledged_within_5 = float(
            (high_waits <= 5).mean()
        )

    else:
        mean_wait = float("nan")
        acknowledged_within_5 = float("nan")

    high_alerted = float(
        selected_high_risk.sum()
    )

    return (
        mean_wait,
        acknowledged_within_5,
        high_alerted
    )


for name in ["cam", "or"]:

    queue_stats = calculate_queue_statistics(
        alerts[name],
        np.zeros(len(y_test)),
        False,
        seed=SEED + 3
    )

    results[name]["ack_mean"] = queue_stats[0]
    results[name]["ack5"] = queue_stats[1]
    results[name]["high_alerted"] = queue_stats[2]
    results[name]["high_total"] = float(high_risk.sum())
    results[name]["interrupts_per_day"] = (
        results[name]["alarms_per_day"]
    )


# Proposed system: risk-prioritized queue.
proposed_risk_alerts = (
    alerts["prop"] & (predicted_levels >= 1)
)

proposed_priorities = (
    predicted_levels.astype(float)
    + score_proposed * 0.1
)

queue_stats = calculate_queue_statistics(
    proposed_risk_alerts,
    proposed_priorities,
    True,
    seed=SEED + 3
)

results["prop"]["ack_mean"] = queue_stats[0]
results["prop"]["ack5"] = queue_stats[1]
results["prop"]["high_alerted"] = queue_stats[2]
results["prop"]["high_total"] = float(high_risk.sum())

results["prop"]["interrupts_per_day"] = float(
    proposed_risk_alerts.sum() / TEST_DAYS
)

results["prop"]["digest_per_day"] = float(
    (
        alerts["prop"]
        & (predicted_levels == 0)
    ).sum() / TEST_DAYS
)


# ============================================================
# 10. HIGH-RISK RECALL
# ============================================================

for name in ["cam", "or", "prop"]:

    if name == "prop":
        selected_alerts = (
            alerts[name] & (predicted_levels >= 1)
        )
    else:
        selected_alerts = alerts[name]

    if high_risk.sum() > 0:

        high_recall = (
            selected_alerts & high_risk
        ).sum() / high_risk.sum()

    else:
        high_recall = float("nan")

    results[name]["high_recall"] = float(high_recall)


# ============================================================
# 11. SAVE EXPERIMENT RESULTS
# ============================================================

json_path = BASE_DIR / "res.json"
roc_path = BASE_DIR / "roc.npy"
pickle_path = BASE_DIR / "out.pkl"

with open(json_path, "w") as file:
    json.dump(
        results,
        file,
        indent=4,
        allow_nan=True
    )

np.save(
    roc_path,
    np.array(
        [
            roc_results[name][:2]
            for name in ["cam", "or", "prop"]
        ],
        dtype=object
    ),
    allow_pickle=True
)

with open(pickle_path, "wb") as file:
    pickle.dump(
        {
            "roc": roc_results,
            "res": results,
            "cm": risk_cm,
        },
        file
    )


# ============================================================
# 12. PRINT FINAL RESULTS
# ============================================================

print("\n" + "=" * 60)
print("BORDER SURVEILLANCE SIMULATION RESULTS")
print("=" * 60)

print("\nExperiment configuration:")
print("Random seed:", SEED)
print("Total simulation days:", DAYS)
print("Training days:", TRAIN_DAYS)
print("Testing days:", TEST_DAYS)
print("Total test samples:", len(y_test))

print("\nModel performance:")

for name in ["cam", "or", "prop"]:

    print(f"\n{name.upper()}")

    for metric, value in results[name].items():

        if isinstance(value, float):
            print(f"{metric:25s}: {value:.4f}")
        else:
            print(f"{metric:25s}: {value}")

print("\nRisk classification accuracy:")
print(f"{risk_accuracy:.4f}")

print("\nRisk classification confusion matrix:")
print(risk_cm)

print("\n" + "=" * 60)
print("FILES GENERATED SUCCESSFULLY")
print("=" * 60)

print("Results JSON:", json_path)
print("ROC data:", roc_path)
print("Pickle data:", pickle_path)