"""World model: predict next-state positions and incoming threats.

Predicts where tracked objects will be in ``horizon_steps`` using their
estimated velocity (constant-velocity extrapolation). Objects whose
predicted position enters the player's zone are reported as incoming
threats with an estimated time-to-impact, plus a rule-based dodge
recommendation — enabling proactive dodging instead of reactive dodging.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gfa.worldmodel.tracker import ObjectTracker, TrackedObject


@dataclass
class Threat:
    """A predicted incoming threat: an object entering the player's zone."""

    label: str
    predicted_x: float
    predicted_y: float
    steps_to_impact: float
    time_to_impact_ms: float
    dodge_direction: str = "left"  # away from the threat's predicted side

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "predicted_x": round(self.predicted_x, 1),
            "predicted_y": round(self.predicted_y, 1),
            "steps_to_impact": round(self.steps_to_impact, 1),
            "time_to_impact_ms": round(self.time_to_impact_ms, 1),
            "dodge_direction": self.dodge_direction,
        }


@dataclass
class WorldPrediction:
    """Full prediction snapshot for one step."""

    step: int
    horizon_steps: float
    predicted_positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    incoming_threats: list[Threat] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "horizon_steps": self.horizon_steps,
            "predicted_positions": {k: (round(v[0], 1), round(v[1], 1)) for k, v in self.predicted_positions.items()},
            "incoming_threats": [t.to_dict() for t in self.incoming_threats],
            "recommendation": self.recommendation,
        }

    def to_text(self) -> str:
        if not self.predicted_positions and not self.incoming_threats:
            return "Predicted: no moving threats"
        parts = [f"Predicted ({self.horizon_steps:g} steps):"]
        for label, (px, py) in self.predicted_positions.items():
            parts.append(f"{label}->({px:.0f},{py:.0f})")
        for t in self.incoming_threats:
            parts.append(f"THREAT {t.label} impact ~{t.time_to_impact_ms:.0f}ms, dodge {t.dodge_direction}")
        if self.recommendation:
            parts.append(f"Recommendation: {self.recommendation}")
        return " ".join(parts)


class WorldModelPredictor:
    """Predicts object positions and threats from tracked motion."""

    def __init__(self, tracker: ObjectTracker | None = None, frame_width: int = 1920,
                 frame_height: int = 1080, player_radius_px: float = 100.0,
                 step_ms: float = 200.0, horizon_steps: float = 3.0):
        self.tracker = tracker or ObjectTracker()
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.player_radius_px = player_radius_px
        self.step_ms = step_ms
        self.horizon_steps = horizon_steps

    def update(self, objects: list, step: int | None = None) -> WorldPrediction:
        """Update tracks from a perception result and return the prediction."""
        tracks = self.tracker.update(objects, step=step)
        pred = self.predict(tracks)
        return pred

    def predict(self, tracks: list[TrackedObject] | None = None) -> WorldPrediction:
        tracks = tracks if tracks is not None else list(self.tracker.tracked.values())
        cx, cy = self.frame_width / 2.0, self.frame_height / 2.0
        predicted: dict[str, tuple[float, float]] = {}
        threats: list[Threat] = []

        for t in tracks:
            px, py = t.predicted_at(self.horizon_steps)
            predicted[t.label] = (px, py)
            # Is this object heading into the player's zone within the horizon?
            dist_now = t.distance_to(cx, cy)
            speed = (t.vx ** 2 + t.vy ** 2) ** 0.5
            # approaching: velocity has a component toward the center
            toward = t.vx * (cx - t.x) + t.vy * (cy - t.y)
            if speed <= 0.1 or toward <= 0:
                continue
            if dist_now <= self.player_radius_px:
                steps_to_impact = 0.0
            else:
                steps_to_impact = (dist_now - self.player_radius_px) / speed
            if steps_to_impact <= self.horizon_steps:
                impact_x = t.x + t.vx * steps_to_impact
                threats.append(Threat(
                    label=t.label,
                    predicted_x=impact_x,
                    predicted_y=t.y + t.vy * steps_to_impact,
                    steps_to_impact=steps_to_impact,
                    time_to_impact_ms=steps_to_impact * self.step_ms,
                    dodge_direction="left" if impact_x > cx else "right",
                ))

        threats.sort(key=lambda t: t.steps_to_impact)
        recommendation = ""
        if threats:
            top = threats[0]
            recommendation = f"dodge {top.dodge_direction}: {top.label} incoming in ~{top.time_to_impact_ms:.0f}ms"

        return WorldPrediction(
            step=self.tracker._step,
            horizon_steps=self.horizon_steps,
            predicted_positions=predicted,
            incoming_threats=threats,
            recommendation=recommendation,
        )
