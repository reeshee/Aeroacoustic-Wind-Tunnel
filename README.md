# Wind Tunnel FFT Analyzer
## Full Design Report can be found here: 
[https://docs.google.com/document/d/1UaNozU0gymNr-kiQ7B2jLVc1SX_kSHz9aF-SaiJXmZw/edit?usp=sharing](url)

A Python application for recording audio from a microphone in a wind tunnel, performing FFT (Fast Fourier Transform) analysis on the recorded signals, and sending/receiving fan speed commands via a COM port (e.g., Arduino).

## Features

- **Record Background Noise**: Capture ambient noise for 5 seconds.
- **Record Operation Noise**: Capture the wind tunnel’s operational noise for 5 seconds.
- **Compute Noise Isolation**: Subtract background noise from operational noise to isolate the wind tunnel’s contribution.
- **Live Fan Speed Control**: Enter a speed to control the fan via the COM port.
- **PWM Output**: Enter a PWM value (0–255) for manual PWM control.
- **Time-Series Plot**: Monitors air speed (m/s) over time on a live graph.
- **Y-Axis Controls**: Dynamically set the y-axis limits for each FFT plot.
- **Reset Experiment**: Stops the fan and clears the FFT/time-series plots.
- **Start New Experiment**: Creates a custom-named folder to store new data.

## Requirements

- Python 3.8+  
- Packages listed in `requirements.txt` (e.g., `numpy`, `sounddevice`, `matplotlib`, `pillow`, etc.)
- A COM port device (like an Arduino) if using fan speed features.

## Installation
Clone this repository:
   ```bash
   git clone https://github.com/username/WindTunnelFFT.git
  ```

Executable apps are available in the /dist folder
**Dev** copy has a debug console, whereas the normal copy is standalone.
