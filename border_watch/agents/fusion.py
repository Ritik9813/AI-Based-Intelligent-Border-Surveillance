import math
from .base import Agent
from .. import config as C

class FusionAgent(Agent):
    """Naive-Bayes fusion of all sensors with behaviour and context.
    Context (night, weather, patrol schedule) shifts what each sensor is expected to read."""
    name, outputs = "fusion", frozenset({"posterior", "threat_prob"})
    SENSOR_VAR = 0.08         # 2 * sigma^2 of smoothed sensor scores
    SPEED_NOISE = 3.0         # tracker speed measurement noise
    PRIOR_WEIGHT = 0.5        # flatten the base-rate prior: a miss costs more than a false alarm

    def posterior(self, track, ctx):
        speed, gs = track.feats.get("speed", 0.0), track.gs
        logp = []
        for c in range(len(C.CLASSES)):
            l = self.PRIOR_WEIGHT * math.log(C.PRIOR[c])
            for k, name in enumerate(C.SENSORS):
                if track.cov[name]:
                    l -= (track.ev[name] - C.sensor_mean(c, k, ctx["night"], ctx["bad"])) ** 2 / self.SENSOR_VAR
            mu, sd = C.SPEED[c]
            sd = math.hypot(sd, self.SPEED_NOISE)
            l -= (speed - mu) ** 2 / (2 * sd ** 2)
            if (gs >= 3) != (c == 1): l -= 3
            if c in (0, 1, 3, 4): l += track.feats.get("heading", 0.0)   # moving toward the border
            st, sp_ = track.feats.get("straight", 1.0), speed
            if sp_ > 8:                                  # erratic path suggests an animal, a straight one a purposeful target
                l += (1.5 if c == 7 else 0.0) if st < .7 else (0.5 if c in (0, 1, 3, 4, 9) else 0.0)
            if track.feats.get("loiter_flag"): l += 3.0 if c == 2 else 0.0
            l -= (0 if c == 9 else 4) if track.auth else (3 if c == 9 else 0)
            logp.append(l)
        m = max(logp); ex = [math.exp(v - m) for v in logp]; z = sum(ex)
        return [v / z for v in ex]

    def process(self, track, ctx):
        self.count += 1
        P = self.posterior(track, ctx)
        return {"posterior": P, "threat_prob": sum(P[:C.N_THREAT])}
