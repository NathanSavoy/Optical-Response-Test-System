#!/usr/bin/env python3
"""
rigol_sled_measure.py

Python script to:
- Trigger an Arduino over serial.
- Query a Rigol oscilloscope over TCP/SCPI (no VISA).
- Record three measurements (one per LED color) per sled increment.
- Repeat for N iterations, save CSV, and plot results.

Dependencies:
  pip install pyserial pandas numpy matplotlib

Tested conceptually; adjust IP/port, serial port, timings, and channel.
"""

import socket
import time
import sys
import csv
from dataclasses import dataclass
from typing import List, Dict
import serial
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime

# =======================
# === USER PARAMETERS ===
# =======================

# Serial (Arduino)
SERIAL_PORT = "/dev/cu.usbserial-2110"   # e.g., "COM6" on Windows, "/dev/ttyUSB0" or "/dev/ttyACM0" on Linux/Mac
SERIAL_BAUD = 115200
SERIAL_TRIGGER_BYTES = b"T"   # what we send to start the Arduino sequence

# Rigol TCP
RIGOL_IP   = "192.168.1.100"   # <-- put your scope IP here
RIGOL_PORT = 5555              # common: 5555 (many Rigol), sometimes 5025

# Measurement plan
N_INCREMENTS = 10
COLORS = ["RED", "GREEN", "BLUE"]      # order Arduino pulses after receiving trigger
SCOPE_CHANNEL = 1                       # which channel your sensor/PD is on (1..4)
MEAS_TYPES = ["VPP", "VRMS"]   # change/extend if desired: ["VPP", "VRMS", "MEAN", "FREQ", ...]
PULSE_DURATION_S   = 0.600   # your pulse length
N_PULSE_SAMPLES    = 6      # reduce to taste; 6–10 works well
MIN_SCPI_INTERVAL  = 0.1   # guardrail between SCPI polls (~25 Hz); tune per scope speed
SAMPLES_CSV_PATH   = "rigol_samples.csv"  # detailed, long-format samples

# Output
now = datetime.datetime.now()
CSV_PATH = f"rigol_run_{now}.csv"
PLOT_PATH = f"rigol_plot{now}.png"
SAMPLES_CSV_PATH   = f"rigol_samples{now}.csv"  # detailed, long-format samples
PLOT_COLOURS = ["red","blue","green"]

# Optional: scope setup (set to True to send a basic setup; safe defaults)
DO_SCOPE_SETUP = True
TIMEBASE_SCALE_S = 0.05    # 50 ms/div (adjust to comfortably see all three pulses)
TRIG_SOURCE_CH  = 1
TRIG_LEVEL_V    = 0.5
TRIG_SLOPE      = "POS"    # "POS" or "NEG"


def wait_for_token(ser, expected: str, timeout_s: float = 3.0) -> bool:
    """
    Block until a line exactly matching `expected` is received over serial.
    Returns True on success, False on timeout.
    """
    deadline = time.time() + timeout_s
    expected = expected.strip()
    buf = b""
    while time.time() < deadline:
        line = ser.readline()  # respects ser.timeout
        if not line:
            continue
        try:
            txt = line.decode(errors="ignore").strip()
        except Exception:
            txt = ""
        if txt == expected:
            return True
        # else ignore any other chatter
    return False

def sample_pulse(scope, ch, meas_types, window_s, n_samples, min_interval_s=0.04):
    """
    Evenly sample SCPI measurements over window_s.
    Returns: list of dicts [{t_rel, <meas_type>: value, ...}, ...]
    """
    if n_samples < 1:
        return []

    t0 = time.time()
    # schedule times as offsets from now
    if n_samples == 1:
        offsets = [window_s / 2.0]  # sample mid-pulse if only one
    else:
        offsets = np.linspace(0, window_s, n_samples, endpoint=False)

    rows = []
    next_allowed = t0
    for off in offsets:
        target = t0 + float(off)
        # sleep until target time
        now = time.time()
        if target > now:
            time.sleep(target - now)

        # simple rate limit so we don't spam SCPI faster than the scope updates
        now = time.time()
        if now < next_allowed:
            time.sleep(next_allowed - now)

        sample = {"t_rel_s": float(time.time() - t0)}
        for mt in meas_types:
            v = rigol_measure(scope, ch, mt)
            sample[mt] = v
        rows.append(sample)

        next_allowed = time.time() + float(min_interval_s)

    return rows


@dataclass
class RigolTCP:
    ip: str
    port: int
    timeout: float = 5.0

    def __post_init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))
        # Some Rigol sockets welcome banner ends with \n; drain it if present
        try:
            time.sleep(0.05)
            self.sock.recv(4096)
        except socket.timeout:
            pass
        except Exception:
            pass

    def write(self, cmd: str):
        """Send SCPI command (no response expected)."""
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.sock.sendall(cmd.encode("ascii"))

    def query(self, cmd: str) -> str:
        """Send SCPI query and return one-line response (stripped)."""
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.sock.sendall(cmd.encode("ascii"))
        chunks = []
        # Many SCPI queries return a single line ending with \n
        # We'll read until \n or timeout
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
        data = b"".join(chunks).decode(errors="ignore").strip()
        return data

    def close(self):
        try:
            self.write(":STOP")
        except Exception:
            pass
        self.sock.close()


def rigol_basic_setup(scope: RigolTCP, ch: int):
    """
    Minimal, conservative setup to make measurements stable.
    Adjust to your experiment as needed.
    """
    # Stop & clear
    scope.write(":STOP")
    scope.write(":CLEar")
    # Timebase
    scope.write(f":TIMebase:SCALe {TIMEBASE_SCALE_S}")
    # Channel on
    scope.write(f":CHANnel{ch}:DISPlay ON")
    # Coupling/DC; bandwidth limit off; probe 1x (tweak as needed)
    scope.write(f":CHANnel{ch}:COUPling DC")
    scope.write(f":CHANnel{ch}:BWLimit OFF")
    scope.write(f":CHANnel{ch}:PROBe 1")
    scope.write(":ACQ:TYPE HRES") # Averaging method
    # Trigger edge
    scope.write(":TRIGger:MODE EDGE")
    scope.write(f":TRIGger:EDGE:SOURce CHANnel{ch}")
    scope.write(f":TRIGger:EDGE:SLOPe {TRIG_SLOPE}")
    scope.write(f":TRIGger:LEVel CHANnel{ch},{TRIG_LEVEL_V}")
    # Run continuous so live measurements update
    scope.write(":RUN")
    # Optional: turn on quick measurements sidebar (model-dependent; harmless if ignored)
    # scope.write(":MEASure:CLEar")


def rigol_measure(scope: RigolTCP, ch: int, meas_type: str) -> float:
    """
    Query a single auto-measurement from the Rigol.
    meas_type examples: VPP, VMAX, VMIN, MEAN, VRMS, FREQ, PER, etc.
    Returns float('nan') if parsing fails.
    """
    cmd = f":MEASure:{meas_type}? CHANnel{ch}"
    resp = scope.query(cmd)
    try:
        # Many Rigol units return plain number or number + units; keep just the float
        # Strip possible commas/semicolons
        clean = resp.replace(",", " ").split()[0]
        return float(clean)
    except Exception:
        return float('nan')


def open_serial(port: str, baud: int) -> serial.Serial:
    ser = serial.Serial(
        port=port,
        baudrate=baud,
        timeout=1.0,
        write_timeout=1.0
    )
    # Give Arduino a moment to reset if it does on port open
    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def main():
    print("=== Rigol + Arduino measurement runner ===")
    print(f"Opening serial: {SERIAL_PORT} @ {SERIAL_BAUD}")
    ser = open_serial(SERIAL_PORT, SERIAL_BAUD)

    print(f"Connecting to Rigol at {RIGOL_IP}:{RIGOL_PORT} ...")
    scope = RigolTCP(RIGOL_IP, RIGOL_PORT, timeout=5.0)

    try:
        if DO_SCOPE_SETUP:
            print("Applying basic scope setup...")
            rigol_basic_setup(scope, SCOPE_CHANNEL)

        rows: List[Dict] = []

        # Collect all detailed samples here; write once at end
        all_samples_long = []  # each row: iteration, color, t_rel_s, <measures...>

        for i in range(1, N_INCREMENTS + 1):
            print(f"\n--- Increment {i}/{N_INCREMENTS} ---")
            ser.reset_input_buffer()
            ser.write(SERIAL_TRIGGER_BYTES)  # e.g., b'T'
            ser.flush()
            print("Sent serial trigger to Arduino.")

            for color in COLORS:
                token = color[0]  # "R","G","B"
                ok = wait_for_token(ser, token, timeout_s=3.0)
                if not ok:
                    print(f"  Timeout waiting for '{token}'. Recording NaNs.")
                    row = {"iteration": i, "color": color}
                    for mt in MEAS_TYPES: row[mt] = float("nan")
                    rows.append(row)
                    continue

                # Take N samples over the 600 ms pulse
                samples = sample_pulse(
                    scope, SCOPE_CHANNEL, MEAS_TYPES,
                    window_s=PULSE_DURATION_S,
                    n_samples=N_PULSE_SAMPLES,
                    min_interval_s=MIN_SCPI_INTERVAL
                )

                # --- Rollup for your existing per-pulse CSV/plot (use median; swap to mean if you want)
                rollup = {"iteration": i, "color": color}
                for mt in MEAS_TYPES:
                    vals = [s[mt] for s in samples if np.isfinite(s.get(mt, np.nan))]
                    rollup[mt] = float(np.median(vals)) if vals else float("nan")
                rows.append(rollup)
                print(f"  {color}: rollup (median over {len(samples)} samples) -> " +
                    ", ".join(f"{mt}={rollup[mt]:.4g}" for mt in MEAS_TYPES))

                # --- Save detailed samples (long format)
                for s in samples:
                    rec = {"iteration": i, "color": color, "t_rel_s": s["t_rel_s"]}
                    for mt in MEAS_TYPES:
                        rec[mt] = s.get(mt, np.nan)
                    all_samples_long.append(rec)

        # ================
        # Save CSV & Plot
        # ================
        df = pd.DataFrame(rows)
        df.to_csv(CSV_PATH, index=False)
        print(f"\nSaved CSV: {CSV_PATH}")
        # Save long-format sample-level CSV for offline analysis
        if all_samples_long:
            df_samples = pd.DataFrame(all_samples_long)
            df_samples.to_csv(SAMPLES_CSV_PATH, index=False)
            print(f"Saved sample-level CSV: {SAMPLES_CSV_PATH}")


        # Plot VPP across iterations for each color
        if "VRMS" in df.columns:
            plt.figure(figsize=(8, 5))
            for color in COLORS:
                sub = df[df["color"] == color].sort_values("iteration")
                plt.plot(sub["iteration"].values, sub["VPP"].values, marker="o", label=color, color=PLOT_COLOURS[COLORS.index(color)])
            plt.xlabel("Iteration")
            plt.ylabel("RMS Voltage (V)")
            plt.title("Rigol VRMS vs. Iteration (per color)")
            plt.grid(True, which="both", linestyle="--", alpha=0.5)
            plt.legend()
            plt.tight_layout()
            plt.savefig(PLOT_PATH, dpi=150)
            print(f"Saved plot: {PLOT_PATH}")
        else:
            print("VRMS not in MEAS_TYPES; skipping plot.")

    finally:
        try:
            scope.close()
        except Exception:
            pass
        try:
            ser.close()
        except Exception:
            pass
        print("Closed connections.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
