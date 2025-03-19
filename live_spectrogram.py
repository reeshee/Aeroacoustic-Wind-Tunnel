import numpy as np
import sounddevice as sd
import time
import matplotlib.pyplot as plt
import queue

# Constants
FS = 96000  # Sampling rate (Hz)
DURATION = 5  # Duration for recording (5 seconds)
N_SAMPLES = int(DURATION * FS)
BIT_DEPTH = 24  # 24-bit recording
ADC_PEAK_VOLTAGE = 5  # Assumed ADC peak voltage
MIC_SENSITIVITY_V_PER_PA = 0.01  # 10 mV/Pa (-40 dB re 1V/Pa)
P_REF = 20e-6  # Reference pressure for 0 dB SPL (Pa)
CALIBRATION_OFFSET = 86 - 81.4

# Ensure audio_queue exists
audio_queue = queue.Queue()

###############################################################################################################

def record_audio(duration=DURATION):
    """Records audio for a given duration and returns the raw waveform."""
    print(f"Recording for {duration} seconds...")
    audio_data = sd.rec(int(duration * FS), samplerate=FS, channels=1, dtype='float32', blocking=True)
    audio_data = audio_data.flatten()  # Convert to 1D array
    return audio_data

def update_plot(ax, line, data, title, fig):
    """Updates the FFT graph in real-time."""
    if len(data) == 0:
        return  # Prevent updates with empty data
    
    data = np.asarray(data)  # Ensure it's a proper NumPy array
    if data.ndim > 1:
        data = data.flatten()  # Flatten any nested structures
    
    line.set_ydata(data)  # Update plot with correct shape
    ax.relim()  # Recompute limits
    ax.autoscale_view()  # Adjust view dynamically
    ax.set_title(title)

    fig.canvas.draw_idle()  # Update the figure

def compute_fft(audio_data, n_window=4096, overlap=0.5):
    """
    Computes FFT with 50% overlap and returns averaged frequency bins and dB SPL values.
    """
    step = int(n_window * (1 - overlap))  # Hop size (50% overlap)
    num_segments = (len(audio_data) - n_window) // step + 1  # Number of overlapping segments

    fft_stack = []  # Store FFT results for averaging

    for i in range(num_segments):
        start = i * step
        segment = audio_data[start : start + n_window]  # Extract segment
        if len(segment) < n_window:
            break  # Ignore incomplete segments

        # Apply Hanning window
        window = np.hanning(n_window)
        windowed_segment = segment * window

        # Convert float to voltage
        voltage_signal = windowed_segment * ADC_PEAK_VOLTAGE

        # Convert to Pascals
        pressure_pa = voltage_signal / MIC_SENSITIVITY_V_PER_PA

        # Compute FFT
        fft_data = np.fft.rfft(pressure_pa)
        mag_pa = np.abs(fft_data) * (2.0 / n_window)  # Normalize
        mag_pa /= np.sqrt(np.mean(window**2))  # RMS correction

        # Convert to dB SPL
        mag_db_spl = 20 * np.log10(np.maximum(mag_pa, P_REF / 1000) / P_REF)
        mag_db_spl += CALIBRATION_OFFSET
        fft_stack.append(mag_db_spl)

    # Average across all segments
    avg_fft = np.mean(fft_stack, axis=0)
    freqs = np.fft.rfftfreq(n_window, 1 / FS)

    return freqs, avg_fft

def save_fft_data(filename, freqs, mag_db_spl):
    """
    Saves frequency bins and dB SPL values to a CSV file.
    Columns: Frequency (Hz), SPL (dB)
    """
    np.savetxt(
        filename,
        np.column_stack((freqs, mag_db_spl)),
        delimiter=",",
        header="Frequency (Hz),SPL (dB)",
        comments="",
        fmt="%.6f"
    )
    print(f"FFT data saved to {filename}")

def save_third_octave_data(filename, center_freqs, band_spl):
    """
    Saves 1/3 octave band center frequencies and SPL values to a CSV file.
    Columns: Center Frequency (Hz), SPL (dB)
    """
    np.savetxt(
        filename,
        np.column_stack((center_freqs, band_spl)),
        delimiter=",",
        header="Center Frequency (Hz),SPL (dB)",
        comments="",
        fmt="%.6f"
    )
    print(f"1/3 Octave data saved to {filename}")

def plot_fft(freqs, mag_db_spl, title="FFT Spectrum"):
    """Plots the FFT spectrum."""
    plt.figure(figsize=(10, 6))
    plt.plot(freqs, mag_db_spl, color='blue', lw=1)
    plt.xscale('log')
    plt.xlim([20, FS / 2])
    plt.ylim([-50, 120])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('SPL (dB)')
    plt.title(title)
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.show()

def compute_1_3_octave_band_spl(freqs, mag_db_spl):
    """
    Averages SPL values in each 1/3 octave band.
    
    :param freqs: FFT frequency bins
    :param mag_db_spl: FFT magnitude SPL values
    :return: center_frequencies & averaged SPL per 1/3 octave band
    """
    # Standard 1/3 octave band center frequencies (ISO 266)
    center_frequencies = np.array([
        31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 
        800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 
        10000, 12500, 16000
    ])

    band_spl = []  # Store averaged SPL per band

    for fc in center_frequencies:
        # Define band edges
        f_low = fc / (2 ** (1 / 6))  # Lower edge of 1/3 octave band
        f_high = fc * (2 ** (1 / 6))  # Upper edge

        # Find indices within this band
        idx = np.where((freqs >= f_low) & (freqs <= f_high))[0]

        if len(idx) > 0:
            # Average SPL in this band
            avg_spl = np.mean(mag_db_spl[idx])
            band_spl.append(avg_spl)
        else:
            band_spl.append(-np.inf)  # If no data, set to -∞

    return center_frequencies, np.array(band_spl)
    
def setup_plot():
    """Initializes a Matplotlib figure with subplots for real-time FFT visualization."""
    fig, axs = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    
    # Top-left: Background noise FFT
    axs[0, 0].set_title("Background Noise FFT")
    axs[0, 0].set_xscale('log')
    axs[0, 0].set_xlim([20, FS / 2])
    axs[0, 0].set_ylim([-50, 120])
    axs[0, 0].set_xlabel('Frequency (Hz)')
    axs[0, 0].set_ylabel('SPL (dB)')
    axs[0, 0].grid(True, which="both", ls="-", alpha=0.5)

    # Top-right: Operation noise FFT
    axs[0, 1].set_title("Operation Noise FFT")
    axs[0, 1].set_xscale('log')
    axs[0, 1].set_xlim([20, FS / 2])
    axs[0, 1].set_ylim([-50, 120])
    axs[0, 1].set_xlabel('Frequency (Hz)')
    axs[0, 1].set_ylabel('SPL (dB)')
    axs[0, 1].grid(True, which="both", ls="-", alpha=0.5)

    # Bottom (Merged): Noise-Isolated FFT
    axs[1, 0].set_title("Noise-Isolated FFT")
    axs[1, 0].set_xscale('log')
    axs[1, 0].set_xlim([20, FS / 2])
    axs[1, 0].set_ylim([-50, 120])
    axs[1, 0].set_xlabel('Frequency (Hz)')
    axs[1, 0].set_ylabel('SPL (dB)')
    axs[1, 0].grid(True, which="both", ls="-", alpha=0.5)

    axs[1, 1].axis("off")  # Disable bottom-right subplot (not needed)

    return fig, axs

def audio_callback(indata, frames, time, status):
    """Callback function for real-time audio capture."""
    if status:
        print("Audio stream status:", status)
    if not audio_queue.full():
        audio_queue.put(indata.copy())
