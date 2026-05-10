"""FocusFrame — the schema emitted by Pipeline. Designed to match the future
MCP server's response shape so we don't reshape twice."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FocusFrame(BaseModel):
    """One processed window. All scalars are channel-averaged unless _per_channel."""

    ts: float = Field(description="Window-end timestamp, seconds (monotonic).")
    alpha: float
    beta: float
    theta: float
    delta: float
    gamma: float
    focus: float = Field(description="Raw F = β/α this window.")
    focus_ema: float = Field(description="EMA-smoothed F.")
    artifact: list[str] = Field(default_factory=list, description="Active artifact flags.")
    artifact_clean: bool
    latency_ms: float = Field(description="Wall-clock from sample-arrival to frame emit.")

    # Channel detail kept optional for the dash; MCP exposes only summaries.
    alpha_per_channel: list[float] | None = None
    beta_per_channel: list[float] | None = None
    gamma_per_channel: list[float] | None = None

    # Frontal-only F (mean of AF7+AF8). Precomputed by Pipeline so the Gatekeeper
    # and Coach can prefer it over the 4-channel mean without recomputing.
    # Optional for backward compat — older serialized frames omit these.
    frontal_focus: float | None = Field(default=None, description="Raw β/α from AF7+AF8.")
    frontal_focus_ema: float | None = Field(default=None, description="EMA-smoothed frontal F.")

    # Affect axes (M4.0). Continuous proxies — NOT discrete emotions. Null when
    # inputs are unavailable (e.g. missing per-channel α at warmup).
    frontal_asymmetry: float | None = Field(
        default=None,
        description="log(α_AF8) − log(α_AF7). Positive = approach/positive valence (Davidson).",
    )
    arousal_index: float | None = Field(
        default=None,
        description="(β + γ) / α. Higher = more activated/alert.",
    )

    # M4.2 — physiological signals from Muse PPG + gyro. All nullable: zero
    # for synthetic, None until rolling buffers warm.
    heart_rate_bpm: float | None = Field(
        default=None, description="Median HR over rolling PPG window."
    )
    hrv_rmssd: float | None = Field(
        default=None, description="RMSSD of inter-beat intervals (ms). Parasympathetic proxy.",
    )
    gyro_max: float | None = Field(
        default=None, description="Max abs angular velocity (deg/s) in window — head-turn intensity.",
    )

    # Relative band power — each band as a fraction of total spectral power.
    # Sums to ~1.0. Bounded 0-1 so the UI can render a meaningful bar without
    # needing per-user calibration. Absolute powers above are kept for raw
    # diagnostics + downstream features that need µV² units.
    delta_rel: float | None = None
    theta_rel: float | None = None
    alpha_rel: float | None = None
    beta_rel: float | None = None
    gamma_rel: float | None = None
