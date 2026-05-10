"""Constants. Single source of truth for sampling + band edges."""
from __future__ import annotations

SAMPLE_RATE_HZ = 256
EEG_CHANNELS = ("TP9", "AF7", "AF8", "TP10")
ACCEL_AXES = ("ACC_X", "ACC_Y", "ACC_Z")
GYRO_AXES = ("GYR_X", "GYR_Y", "GYR_Z")
PPG_CHANNELS = ("PPG_IR1", "PPG_IR2", "PPG_AMB")
PPG_RATE_HZ = 64
GYRO_RATE_HZ = 52

WINDOW_SECONDS = 1.0
STRIDE_SECONDS = 0.25
WINDOW_SAMPLES = int(SAMPLE_RATE_HZ * WINDOW_SECONDS)
STRIDE_SAMPLES = int(SAMPLE_RATE_HZ * STRIDE_SECONDS)

DISPLAY_SECONDS = 4.0  # how much raw EEG history to retain for the dash plot

BANDS_HZ = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}

NOTCH_HZ = 60.0
BANDPASS_HZ = (1.0, 40.0)

FOCUS_EMA_ALPHA = 0.3

MOTION_ACCEL_G_THRESH = 0.15
# Angular velocity threshold for the gyro-based motion flag. Resting-head gyro
# magnitude is <10 deg/s; deliberate head turn → 50-200 deg/s. 60 catches
# meaningful turns without false-positiving slight breathing wobble.
MOTION_GYRO_DPS_THRESH = 60.0
BLINK_UV_THRESH = 150.0
# JAW now per-channel: std of sample-to-sample diff for ONE channel.
# Real jaw clench affects all 4 channels; we require ≥3 channels above
# this threshold to flag (one hot channel = sensor noise, not jaw).
# Empirically: clean Muse channels diff-std ~10-50 µV; jaw push past 100.
JAW_HF_PER_CHANNEL_UV = 100.0
JAW_MIN_CHANNELS = 3

LATENCY_BUDGET_MS = 500
