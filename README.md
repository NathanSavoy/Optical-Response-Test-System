# Optical Response Test System
**Automated RGB–LDR Characterization using Python + Arduino + Rigol DS1054Z**

---

## Overview
This project implements a **fully automated optical test bench** for characterizing the response of a light-dependent resistor (LDR) under **RGB LED illumination**.  
A Python master script coordinates test execution, while an Arduino sub-controller handles LED pulsing and mechanical actuation.  
The Rigol DS1054Z oscilloscope is controlled via **SCPI over TCP**, providing synchronized, noise-reduced voltage measurements.

Originally developed as a LabVIEW exercise in test design and automation, the system was later migrated to Python for greater flexibility, open-source portability, and deeper insight into instrument control protocols.

---

## System Architecture

PC (Python Master)
│
├── Serial → Arduino (Trigger: 'T')
│ ├── Increments sled actuator
│ ├── Pulses RGB LEDs (600 ms each)
│ └── Sends handshake tokens 'R', 'G', 'B'
│
├── TCP/SCPI → Rigol DS1054Z Oscilloscope
│ ├── Configured in HRES mode for low-noise acquisition
│ ├── Measures Vpp / Vmax / Vmin across the LDR
│ └── Returns measurements to Python
│
└── Output
├── rigol_run.csv – Per-color averaged results
├── rigol_samples.csv – Full time-resolved samples
└── rigol_plot.png – Matplotlib summary plot


---

## Files

| File | Description |
|------|--------------|
| `rigol_sled_measure.py` | Main Python control script – handles serial, SCPI, sampling, CSV logging, and plotting |
| `arduino_subcontroller.ino` | Arduino firmware – receives triggers, runs RGB pulse sequence, returns handshake tokens |
| `requirements.txt` | Python dependencies (`pyserial`, `pandas`, `numpy`, `matplotlib`) |
| `README.md` | This file |

---

## How It Works
1. Python sends a serial `'T'` to the Arduino.  
2. Arduino increments the sled, then pulses **Red**, **Green**, and **Blue** LEDs for ~600 ms each.  
3. For each pulse:
   - Arduino prints a color token (`R`, `G`, `B`).
   - Python waits for the token, then samples the Rigol measurements 6–10 times during the pulse.
4. Data is averaged, logged, and plotted automatically.

---

## Example Output

- **`rigol_plot.png`** — Voltage (Vpp) vs. iteration per color  
  Blue consistently yields the **lowest voltage**, green is intermediate, and red the **highest**, indicating spectral response differences in the LDR.

---

## Setup Instructions

1. **Connect Hardware**
   - Arduino via USB (check port name in `SERIAL_PORT`)
   - Rigol DS1054Z via LAN (confirm IP and port 5555)
   - LDR/LED circuit on CH1 of the scope

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt


## Run

python rigol_sled_measure.py

## View Results

  - Plots and csv files are generated automatically in the working directory.
