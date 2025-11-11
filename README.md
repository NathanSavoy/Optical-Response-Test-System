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

