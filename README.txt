# Live FFT Analyzer

## Overview

The Live FFT Analyzer is a Python application that records audio in real time, computes its Fast Fourier Transform (FFT), and displays the results using a graphical interface. It also calculates noise isolation by subtracting background noise from operation noise. This tool is especially useful for applications such as aeroacoustic analysis.

## IMPORTANT - DO THIS BEFORE ANYTHING ELSE

1. OPEN TERMINAL, NAVIGATE TO THE DIRECTORY /LIVE_FFT_ANALYZER
run the following:
pip install -r requirements.txt

2. OPEN THIS DIRECTORY AND RUN THE FILE: /dist/run_analysis.exe
  Run this app to launch the testing window.
  Record Background audio first until graph appears, then record Operation audio until graph appears. Finally, click compute isolation.
  Data is stored in /dist

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

## FILE INFORMATION:
- **live_spectrogram.py**  
  Contains the core functions for audio recording, FFT computation, and plotting.

- **run_analysis.py**  
  Implements the GUI using Tkinter, handles audio recording (background and operation), computes noise isolation, and saves the results to timestamped files.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

## Requirements
- **Python 3.x**
- **Dependencies:**
  - numpy
  - matplotlib
  - sounddevice
  - tkinter (usually included with standard Python installations)

You can install the required Python packages using pip:

## if there are any errors:
pip install numpy matplotlib sounddevice


