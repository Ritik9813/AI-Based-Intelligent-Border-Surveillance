from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Track:
    id: int
    obs: int = 0
    ev: dict = field(default_factory=lambda: {"cam": 0., "thermal": 0., "radar": 0., "fence": 0., "rf": 0.})
    cov: dict = field(default_factory=lambda: {k: False for k in ("cam", "thermal", "radar", "fence", "rf")})
    pos: list = field(default_factory=list)       # (t, x, y)
    gs: int = 1
    auth: bool = False
    feats: dict = field(default_factory=dict)
    post: Optional[list] = None
    th: float = 0.0
    risk: float = 0.0
    lvl: int = 0
    raw: bool = False
    alert: Optional["Alert"] = None
    closed: bool = False

@dataclass
class Alert:
    id: int
    t0: float
    lvl: object                    # 0..3, or "U" for an unranked raw alarm
    th: float = 0.0
    risk: float = 0.0
    top: int = 0
    status: str = "new"            # new, ack, done, digest, lost, withdrawn
    escalated: bool = False
    channels: list = field(default_factory=list)
    t_ack: Optional[float] = None
