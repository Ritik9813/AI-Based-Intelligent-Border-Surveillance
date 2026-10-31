"""Simulated border sector: moving entities and noisy multi-sensor readings."""
import math, random
from . import config as C

class Entity:
    def __init__(self, id, cls, rng):
        self.id, self.cls = id, cls
        self.x, self.y, self.vx, self.vy = 60 + rng.random() * 780, -8., 0., 0.
        self.age, self.life, self.gs, self.hold, self.ang, self.next_obs = 0., 400., 1, 0., 0., 0.5
        self.auth = rng.random() < (0.85 if cls == 9 else 0.02)
        r = rng.random
        if cls in (0, 1):
            self.vy, self.vx = 14 + r() * 3, (r() - .5) * 6
            if cls == 1: self.gs = rng.randint(3, 7)
        elif cls == 2: self.x, self.vy, self.hold = 80 + r() * 740, 22., 45.
        elif cls == 3: self.vy, self.vx = 48 + r() * 10, (r() - .5) * 14
        elif cls == 4:
            left = r() < .5; self.x = 20. if left else 880.; self.vx = 24. if left else -24.; self.vy = 26.
        elif cls == 5: self.x, self.y, self.life = 100 + r() * 700, 290 + r() * 40, 100.
        elif cls == 6: self.x, self.y, self.life = 100 + r() * 700, C.FENCE_Y, 70.
        elif cls == 7: self.y, self.ang, self.life = 130 + r() * 250, r() * 6.28, 45.
        elif cls == 8: self.x, self.y, self.life = 100 + r() * 700, 170 + r() * 160, 9.
        elif cls == 9: self.x, self.y, self.vx = -5., 345., 44 + r() * 8

class World:
    def __init__(self, seed=None, rate_scale=1.0):
        self.rate_scale = rate_scale
        self.rng = random.Random(seed)
        self.t, self.entities, self.next_id = 0., [], 1
        self.night = self.bad_weather = False
        self.auto = True
        self.truth = {}                      # id -> true class (used only for scoring and feedback)
        self.n_threats = 0
        self._nt, self._nb = 3., 1.

    def spawn(self, cls):
        e = Entity(self.next_id, cls, self.rng); self.next_id += 1
        self.entities.append(e); self.truth[e.id] = cls
        self.n_threats += cls < C.N_THREAT
        return e

    def coverage(self, e):
        d = min(math.hypot(e.x - tx, e.y - ty) for tx, ty in C.TOWERS)
        dr = math.hypot(e.x - C.RADAR[0], e.y - C.RADAR[1])
        return [d < 250, d < 250, dr < 400, abs(e.y - C.FENCE_Y) < 28, dr < 430]

    def read(self, e):
        """Noisy readings from every sensor that covers the entity, or None."""
        cov = self.coverage(e)
        if not any(cov): return None
        rd = {}
        for k, name in enumerate(C.SENSORS):
            if cov[k]:
                sg = .22 if (k == 0 and self.night) else .15
                rd[name] = min(1, max(0, C.sensor_mean(e.cls, k, self.night, self.bad_weather) + self.rng.gauss(0, sg)))
            else:
                rd[name] = None
        return dict(t=self.t, x=e.x + self.rng.gauss(0, 1.5), y=e.y + self.rng.gauss(0, 1.5),
                    gs=e.gs, auth=e.auth, readings=rd)

    def step(self, dt=0.1):
        """Advance time. Returns (observations due, entities that finished)."""
        r = self.rng; self.t += dt; obs, done = [], []
        if self.auto:
            self._nt -= dt; self._nb -= dt
            if self._nt <= 0: self.spawn(r.randrange(7)); self._nt = (10 + r.random() * 10) * self.rate_scale
            if self._nb <= 0:
                q = r.random(); self.spawn(7 if q < .5 else 8 if q < .85 else 9); self._nb = (2.5 + r.random() * 3) * self.rate_scale
        for e in self.entities:
            e.age += dt; e.x += e.vx * dt; e.y += e.vy * dt
            if e.cls == 2:
                if e.vy > 0 and e.y >= 212: e.vy = e.vx = 0.
                if e.vy == 0 and e.age > e.hold + 9: e.vy = -12.
            elif e.cls == 7:
                e.ang += (r.random() - .5) * dt * 14
                e.vx, e.vy = math.cos(e.ang) * 22, math.sin(e.ang) * 22
                e.y = min(430, max(110, e.y))
            elif e.cls in (0, 1) and e.y > C.FENCE_Y + 10: e.vx = 0.
            if e.age >= e.next_obs:
                e.next_obs += 0.5
                rd = self.read(e)
                if rd: obs.append((e, rd))
            if e.x < -30 or e.x > C.W + 30 or e.y < -30 or e.y > C.H + 30 or e.age > e.life:
                done.append(e)
        if done: self.entities = [e for e in self.entities if e not in done]
        return obs, done
