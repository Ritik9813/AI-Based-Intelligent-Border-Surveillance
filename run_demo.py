"""Headless demo: raw-alarm mode versus the multi-agent mode with one simulated operator.
   python run_demo.py [--hours 4] [--seed 1] [--night]"""
import argparse, csv, random
from border_watch.simulator import World
from border_watch.agents import Orchestrator
from border_watch import config as C

def run(agents_on, hours, seed, night, rate=3.0, service=15.0):
    """One operator: handles one alert at a time (mean `service` s), highest level first when agents are on,
    first-come-first-served in raw mode. The operator judges each alert correctly 95% of the time."""
    w = World(seed, rate_scale=rate); w.night = night; o = Orchestrator(w); o.agents_on = agents_on
    rng = random.Random(seed + 99); busy_until, cur, busy, waits = 0.0, None, 0.0, []
    for _ in range(int(hours * 3600 / 0.1)):
        o.step(0.1)
        if cur is None:
            q = o.alert.open_alerts()
            if q:
                key = (lambda a: a.t0) if not agents_on else (lambda a: (-(a.lvl if a.lvl != "U" else 0), a.t0))
                cur = min(q, key=key); dur = rng.expovariate(1 / service)
                busy_until = w.t + dur; busy += dur
                if cur.lvl != "U" and cur.lvl >= 2: waits.append(w.t - cur.t0)
                o.operator(cur.id, "ack")
        elif w.t >= busy_until:
            truth_threat = w.truth[cur.id] < C.N_THREAT
            says_threat = truth_threat if rng.random() < .95 else not truth_threat
            o.operator(cur.id, "go" if says_threat else "no"); cur = None
    k = o.kpis(); k["wait_high"] = round(sum(waits) / len(waits), 1) if waits else None
    k["busy"] = round(100 * busy / (hours * 3600))
    return k, o

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--hours", type=float, default=4); p.add_argument("--seed", type=int, default=1)
    p.add_argument("--night", action="store_true"); a = p.parse_args()
    cols = [("threats", "Threats"), ("handled", "Handled"), ("missed", "Missed"), ("raw", "Raw alarms"), ("sent", "To operator"),
            ("filtered", "Filtered"), ("false_dispatch", "False dispatch"), ("wait_high", "Wait High/Crit s"), ("busy", "Operator busy %")]
    print(f"\nSimulated {a.hours:g} h, seed {a.seed}, {'night' if a.night else 'day'}, one operator\n")
    print(f"{'Mode':<12}" + "".join(f"{n:>17}" for _, n in cols))
    for on in (False, True):
        k, o = run(on, a.hours, a.seed, a.night)
        print(f"{'Agents ON' if on else 'Raw alarms':<12}" + "".join(f"{str(k[c]):>17}" for c, _ in cols))
    if o.feedback:
        with open("feedback_labels.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(o.feedback[0])); wr.writeheader(); wr.writerows(o.feedback)
        print(f"\nOperator feedback saved to feedback_labels.csv ({len(o.feedback)} labelled rows, ready for retraining)")
