import sys
import os
import csv
import numpy as np
import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog
import sounddevice as sd
import threading
import time
import matplotlib
matplotlib.use("TkAgg")  # Use the TkAgg backend for embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

# Pillow for loading images
from PIL import Image, ImageTk

# ------------------------------
# Helper to locate resources (for PyInstaller onefile)
# ------------------------------
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        # When running in a PyInstaller bundle, sys._MEIPASS is where files are extracted
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ------------------------------
# Import your existing FFT functions
# ------------------------------
from live_spectrogram import (
    compute_fft,
    compute_1_3_octave_band_spl,
    save_fft_data,
    save_third_octave_data,
    setup_plot,
    update_plot,
    audio_callback,
    audio_queue
)

# ------------------------------
# Import the COM port module for fan speed control
# ------------------------------
from com_port import ComPortHandler

# ------------------------------
# Global Variables for Experiment Data
# ------------------------------
output_folder = None
background_spl = None
operation_spl = None

BACKGROUND_FFT_FILE = None
OPERATION_FFT_FILE = None
NOISE_ISOLATED_FFT_FILE = None
NOISE_ISOLATED_THIRDOCT_FILE = None

# ------------------------------
# Global Variables for COM Port / Sensor Data
# ------------------------------
current_air_speed = None  # Latest air speed value (float) or "Sensor Missing"
last_update_time = 0      # Time when a new value was received
last_speed = None         # Last stable air speed
current_pwm = None        # Latest PWM value received from Arduino

# ------------------------------
# Global Variables for Fan Speed Recording
# ------------------------------
recording_fan_speed = False
record_start_time = None
fan_speed_csv_file = None
fan_speed_csv_writer = None
fan_speed_record_thread = None

experiment_start_time = None
time_series = []
speed_series = []
time_speed_line = None  # This will be the red line for the time-series plot

# ------------------------------
# Experiment Folder Functions
# ------------------------------
def set_output_folder(folder):
    """Updates global file paths based on the new experiment folder."""
    global BACKGROUND_FFT_FILE, OPERATION_FFT_FILE, NOISE_ISOLATED_FFT_FILE, NOISE_ISOLATED_THIRDOCT_FILE
    BACKGROUND_FFT_FILE = os.path.join(folder, "background_fft.csv")
    OPERATION_FFT_FILE = os.path.join(folder, "operation_fft.csv")
    NOISE_ISOLATED_FFT_FILE = os.path.join(folder, "noise_isolated_fft.csv")
    NOISE_ISOLATED_THIRDOCT_FILE = os.path.join(folder, "noise_isolated_thirdoct.csv")

def start_new_experiment(self):
    from tkinter import simpledialog
    custom_name = simpledialog.askstring("Experiment Name", "Enter a custom experiment name:")
    if custom_name is None or custom_name.strip() == "":
        start_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        custom_name = f"experiment_{start_time_str}"
    self.output_folder = custom_name
    os.makedirs(self.output_folder, exist_ok=True)
    self.set_output_folder(self.output_folder)
    self.experiment_start_time = time.time()
    self.time_series = []
    self.speed_series = []
    messagebox.showinfo("New Experiment", f"New experiment folder created:\n{self.output_folder}")

def reset_experiment():
    """Stops the fan and resets all graphs (but does not start a new experiment)."""
    try:
        com_handler.send_fan_speed(0)  # Stop the fan
    except Exception as e:
        messagebox.showerror("Error", f"Could not stop the fan: {e}")
    # Reset FFT plots by clearing their data (here we simply set empty arrays)
    update_plot(axs[0,0], background_plot, np.array([]), "Background Noise FFT", fig)
    update_plot(axs[0,1], operation_plot, np.array([]), "Operation Noise FFT", fig)
    update_plot(axs[1,0], noise_isolated_plot, np.array([]), "Noise-Isolated FFT", fig)
    # Reset the time-series plot (assuming you use time_speed_line for Air Speed vs Time)
    global time_series, speed_series
    time_series = []
    speed_series = []
    time_speed_line.set_data([], [])
    canvas.draw()

# ------------------------------
# FFT Recording Functions
# ------------------------------
def record_background():
    if output_folder is None:
        messagebox.showerror("Error", "Please start a new experiment first!")
        return

    def record():
        global background_spl
        stream = sd.InputStream(samplerate=96000, channels=1, callback=audio_callback, blocksize=4096)
        collected_audio = []
        with stream:
            start_t = time.time()
            while time.time() - start_t < 5:
                while not audio_queue.empty():
                    collected_audio.append(audio_queue.get().flatten())
                time.sleep(0.01)
        if collected_audio:
            full_audio = np.concatenate(collected_audio)
            _, background_spl = compute_fft(full_audio)
            root.after(0, lambda: update_plot(axs[0, 0], background_plot, background_spl, "Background Noise FFT", fig))
    threading.Thread(target=record, daemon=True).start()

def record_operation():
    if output_folder is None:
        messagebox.showerror("Error", "Please start a new experiment first!")
        return

    def record():
        global operation_spl
        stream = sd.InputStream(samplerate=96000, channels=1, callback=audio_callback, blocksize=4096)
        collected_audio = []
        with stream:
            start_t = time.time()
            while time.time() - start_t < 5:
                while not audio_queue.empty():
                    collected_audio.append(audio_queue.get().flatten())
                time.sleep(0.01)
        if collected_audio:
            full_audio = np.concatenate(collected_audio)
            _, operation_spl = compute_fft(full_audio)
            root.after(0, lambda: update_plot(axs[0, 1], operation_plot, operation_spl, "Operation Noise FFT", fig))
    threading.Thread(target=record, daemon=True).start()

def compute_noise_isolation():
    if output_folder is None:
        messagebox.showerror("Error", "Please start a new experiment first!")
        return
    if background_spl is None or operation_spl is None:
        messagebox.showerror("Error", "Please record both background and operation noise first!")
        return
    noise_isolated_spl = operation_spl - background_spl
    update_plot(axs[1, 0], noise_isolated_plot, noise_isolated_spl, "Noise-Isolated FFT", fig)
    freqs = np.fft.rfftfreq(4096, 1 / 96000)
    save_fft_data(BACKGROUND_FFT_FILE, freqs, background_spl)
    save_fft_data(OPERATION_FFT_FILE, freqs, operation_spl)
    save_fft_data(NOISE_ISOLATED_FFT_FILE, freqs, noise_isolated_spl)
    center_freqs, thirdoct_spl = compute_1_3_octave_band_spl(freqs, noise_isolated_spl)
    save_third_octave_data(NOISE_ISOLATED_THIRDOCT_FILE, center_freqs, thirdoct_spl)
    fig.savefig(os.path.join(output_folder, "fft_analysis.png"), dpi=300)
    messagebox.showinfo("Completed", f"Analysis complete! Results saved in {output_folder}")

# ------------------------------
# COM Port Fan Speed & PWM Section
# ------------------------------
def handle_serial_data(data):
    """
    Callback for COM port data.
    Expects sensor readings prefixed with "AD" (e.g., "AD1.01")
    or PWM signals prefixed with "PWM" (e.g., "PWM180").
    """
    global current_air_speed, last_update_time, last_speed, current_pwm
    try:
        data = data.strip()
        if data.startswith("AD"):
            try:
                sensorValue = float(data[2:])
                current_air_speed = sensorValue
                if last_speed is None or abs(sensorValue - last_speed) > 0.1:
                    last_speed = sensorValue
                    last_update_time = time.time()
            except ValueError:
                current_air_speed = data
        elif data.startswith("PWM"):
            try:
                current_pwm = int(data[3:])
                root.after(0, lambda: pwm_status_label.config(text=f"PWM: {current_pwm}"))
            except ValueError:
                current_pwm = data
        else:
            print("Arduino Console:", data)
        root.after(0, update_fan_speed_label)
    except Exception as e:
        print("Error in handle_serial_data:", e)

def update_fan_speed_label():
    """
    Updates the air speed status label.
    If the value has not changed significantly for 3 seconds, append "(Stable)".
    """
    if current_air_speed == "Sensor Missing":
        fan_speed_status_label.config(text="Air Speed: Sensor Missing")
    else:
        if isinstance(current_air_speed, (int, float, np.float64)):
            if time.time() - last_update_time >= 3:
                fan_speed_status_label.config(text=f"Air Speed: {current_air_speed} (Stable)")
            else:
                fan_speed_status_label.config(text=f"Air Speed: {current_air_speed}")
        else:
            fan_speed_status_label.config(text=str(current_air_speed))

def set_fan_speed():
    """Sends the entered fan speed to the Arduino via COM port (integer only)."""
    try:
        speed_val = float(fan_speed_entry.get())
        com_handler.send_fan_speed(speed_val)
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a valid speed for fan speed.")
    except Exception as e:
        messagebox.showerror("Error", f"Unexpected error: {e}")

def periodic_fan_check():
    """
    Periodically update the air speed status label and the time-series plot.
    Called via root.after().
    """
    update_fan_speed_label()
    if experiment_start_time is not None and isinstance(current_air_speed, (int, float)):
        t = time.time() - experiment_start_time
        time_series.append(t)
        speed_series.append(current_air_speed)
        time_speed_line.set_data(time_series, speed_series)
        axs[1,1].set_xlim(0, t + 1)
    canvas.draw()
    root.after(125, periodic_fan_check)

def stop_fan():
    """Stops the fan by sending a speed command of 0."""
    try:
        com_handler.send_fan_speed(0)
        fan_speed_entry.delete(0, tk.END)
        fan_speed_entry.insert(0, "0")
    except Exception as e:
        messagebox.showerror("Error", f"Could not stop the fan: {e}")

# ------------------------------
# PWM Controls Section
# ------------------------------
def set_pwm_signal():
    """Sends the entered PWM signal to the Arduino with prefix 'MP' (e.g., MP50)."""
    try:
        pwm_val = int(pwm_entry.get())
        if pwm_val < 0 or pwm_val > 255:
            messagebox.showerror("Input Error", "Please enter a number between 0 and 255 for PWM.")
            return
        command = f"MP{pwm_val}\n"
        if com_handler.ser and com_handler.ser.is_open:
            com_handler.ser.write(command.encode('utf-8'))
            print(f"Sent PWM signal: {command.strip()}")
        else:
            print("Serial port is not open. Cannot send PWM signal.")
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a valid integer for PWM.")
    except Exception as e:
        print("Error sending PWM signal:", e)

# ------------------------------
# Fan Speed Recording Functions
# ------------------------------
def record_fan_speed_loop():
    global recording_fan_speed, record_start_time, fan_speed_csv_file, fan_speed_csv_writer
    while recording_fan_speed:
        elapsed = time.time() - record_start_time
        try:
            if current_air_speed is not None and isinstance(current_air_speed, (int, float)):
                fan_speed_csv_writer.writerow([f"{elapsed:.2f}", f"{current_air_speed:.2f}"])
                fan_speed_csv_file.flush()
        except Exception as e:
            print("Error writing to CSV:", e)
        record_timer_label.config(text=f"Recording time: {int(elapsed)} s")
        time.sleep(0.125)

def toggle_record_fan_speed():
    global recording_fan_speed, record_start_time, fan_speed_csv_file, fan_speed_csv_writer, fan_speed_record_thread
    if not recording_fan_speed:
        if output_folder is None:
            messagebox.showerror("Error", "Please start a new experiment first!")
            return
        recording_fan_speed = True
        record_start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(output_folder, f"fan_speed_record_{timestamp}.csv")
        try:
            fan_speed_csv_file = open(filename, mode='w', newline='')
            fan_speed_csv_writer = csv.writer(fan_speed_csv_file)
            fan_speed_csv_writer.writerow(["Time (s)", "Air Speed (m/s)"])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file for recording: {e}")
            recording_fan_speed = False
            return
        record_fan_speed_button.config(image=rec_fan_speed_img_tk)  # optional if you want to swap an image
        fan_speed_record_thread = threading.Thread(target=record_fan_speed_loop, daemon=True)
        fan_speed_record_thread.start()
    else:
        recording_fan_speed = False
        try:
            if fan_speed_csv_file:
                fan_speed_csv_file.close()
        except Exception as e:
            print("Error closing CSV file:", e)
        record_fan_speed_button.config(image=rec_fan_speed_img_tk)  # revert to original image
        record_timer_label.config(text="Recording time: 0 s")

def set_y_axis_specific():
    """Prompts the user for which plot to update and applies y-axis limits accordingly."""
    choice = simpledialog.askstring("Select Plot", "Enter plot type:\nB - Background\nO - Operation\nI - Isolated")
    if choice is None:
        return  # User cancelled

    try:
        y_min = float(ymin_entry.get())
        y_max = float(ymax_entry.get())
    except Exception as e:
        messagebox.showerror("Input Error", f"Error converting y-axis values: {e}")
        return

    choice = choice.upper().strip()
    if choice == "B":
        axs[0, 0].set_ylim(y_min, y_max)
    elif choice == "O":
        axs[0, 1].set_ylim(y_min, y_max)
    elif choice == "I":
        axs[1, 0].set_ylim(y_min, y_max)
    else:
        messagebox.showerror("Invalid Choice", "Please enter one of B, O, or I")
        return

    canvas.draw()

# ------------------------------
# COM Port Handler
# ------------------------------
def set_com_port():
    global com_handler
    new_port = com_port_entry.get().strip()
    if not new_port:
        messagebox.showerror("Input Error", "Please enter a valid COM port (e.g., COM3).")
        return
    # Close the current connection if open
    if com_handler:
        com_handler.close()
    # Create a new handler using the new port
    com_handler = ComPortHandler(port=new_port, baudrate=115200, timeout=1, callback=handle_serial_data)
    com_handler.open()
    messagebox.showinfo("COM Port Changed", f"COM port changed to {new_port}")

com_handler = ComPortHandler(port="COM3", baudrate=115200, timeout=1, callback=handle_serial_data)
com_handler.open()

# ------------------------------
# MAIN WINDOW SETUP
# ------------------------------
root = tk.Tk()
root.title("Live FFT Analyzer")
root.state("zoomed")
# Create a menubar
menubar = tk.Menu(root)

# File menu with "Reset Experiment"
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Reset Experiment", command=reset_experiment)
menubar.add_cascade(label="File", menu=file_menu)

# Tools menu (empty for now)
tools_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Tools", menu=tools_menu)

# Help menu with an About option
help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Wind Tunnel FFT v0.96"))
menubar.add_cascade(label="Help", menu=help_menu)

# Attach the menubar to the root window
root.config(menu=menubar)

# Dark background for entire window
root.configure(bg="#2b2b2b")

# Create frames with dark backgrounds
left_frame = tk.Frame(root, bg="#2b2b2b")
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

right_frame = tk.Frame(root, bg="#2b2b2b")
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# Create the figure & embed it
fig, axs = setup_plot()
fig.set_constrained_layout(True)

# Make figure background black
fig.patch.set_facecolor("#000000")

# For each subplot, set background black & text white
for row in axs:
    for ax in row:
        ax.set_facecolor("#000000")
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')
        for spine in ax.spines.values():
            spine.set_color('white')

canvas = FigureCanvasTkAgg(fig, master=right_frame)
canvas.draw()
# Make the canvas background dark
canvas.get_tk_widget().configure(bg="#2b2b2b", highlightthickness=0)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

toolbar = NavigationToolbar2Tk(canvas, right_frame)
# Darken the toolbar as well
toolbar.configure(bg="#2b2b2b")
toolbar.update()
toolbar.pack(side=tk.TOP, fill=tk.X)

# Create plot lines
freqs = np.fft.rfftfreq(4096, 1 / 96000)
background_spl = np.full_like(freqs, -50)
operation_spl = np.full_like(freqs, -50)
noise_isolated_spl = np.full_like(freqs, -50)

background_plot, = axs[0, 0].plot(freqs, background_spl, color='blue', lw=1)
operation_plot, = axs[0, 1].plot(freqs, operation_spl, color='blue', lw=1)
noise_isolated_plot, = axs[1, 0].plot(freqs, noise_isolated_spl, color='blue', lw=1)

for freq_ax in [axs[0,0], axs[0,1], axs[1,0]]:
    freq_ax.axvspan(1, 1715, facecolor='gray', alpha=0.3)

# Configure the bottom-right subplot for time-series (Air Speed vs. Time)
axs[1,1].axis("on")
time_speed_line, = axs[1,1].plot([], [], color='red', lw=2)
axs[1,1].set_ylim(-1, 11)
axs[1,1].set_xlabel("Time (s)", color='white')
axs[1,1].set_ylabel("Air Speed (m/s)", color='white')
axs[1,1].set_title("Air Speed vs. Time", color='white')

# ------------------------------
# LOAD & ATTACH BUTTON IMAGES
# ------------------------------
try:
    # For 389×74 images (scale 1.58)
    start_experiment_img = Image.open(resource_path("assets/Start Experiment.png"))
    w, h = start_experiment_img.size
    start_experiment_img = start_experiment_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    start_experiment_img_tk = ImageTk.PhotoImage(start_experiment_img)

    rec_back_img = Image.open(resource_path("assets/Record Background Noise.png"))
    w, h = rec_back_img.size
    rec_back_img = rec_back_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    rec_back_img_tk = ImageTk.PhotoImage(rec_back_img)

    rec_oper_img = Image.open(resource_path("assets/Record Operation Noise.png"))
    w, h = rec_oper_img.size
    rec_oper_img = rec_oper_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    rec_oper_img_tk = ImageTk.PhotoImage(rec_oper_img)

    comp_noise_img = Image.open(resource_path("assets/Compute Noise Isolation.png"))
    w, h = comp_noise_img.size
    comp_noise_img = comp_noise_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    comp_noise_img_tk = ImageTk.PhotoImage(comp_noise_img)

    rec_fan_speed_img = Image.open(resource_path("assets/Record Fan Speed.png"))
    w, h = rec_fan_speed_img.size
    rec_fan_speed_img = rec_fan_speed_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    rec_fan_speed_img_tk = ImageTk.PhotoImage(rec_fan_speed_img)

    set_pwm_img = Image.open(resource_path("assets/Set PWM.png"))
    w, h = set_pwm_img.size
    set_pwm_img = set_pwm_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    set_pwm_img_tk = ImageTk.PhotoImage(set_pwm_img)

    set_com_img = Image.open(resource_path("assets/Set COM.png"))
    w, h = set_com_img.size
    set_com_img = set_com_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    set_com_img_tk = ImageTk.PhotoImage(set_com_img)

    set_y_axis_img = Image.open(resource_path("assets/Set Y AXIS.png"))
    w, h = set_y_axis_img.size
    set_y_axis_img = set_y_axis_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    set_y_axis_img_tk = ImageTk.PhotoImage(set_y_axis_img)

    # For 176×161 images (scale 1.58)
    set_fan_img = Image.open(resource_path("assets/Set Fan Speed.png"))
    w, h = set_fan_img.size
    set_fan_img = set_fan_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    set_fan_img_tk = ImageTk.PhotoImage(set_fan_img)

    stop_fan_img = Image.open(resource_path("assets/Stop Fan.png"))
    w, h = stop_fan_img.size
    stop_fan_img = stop_fan_img.resize((int(w / 1.58), int(h / 1.58)), Image.Resampling.LANCZOS)
    stop_fan_img_tk = ImageTk.PhotoImage(stop_fan_img)

except Exception as e:
    print("Image loading error:", e)
    start_experiment_img_tk = None
    rec_back_img_tk = None
    rec_oper_img_tk = None
    comp_noise_img_tk = None
    rec_fan_speed_img_tk = None
    set_pwm_img_tk = None
    set_com_img_tk = None
    set_y_axis_img_tk = None
    set_fan_img_tk = None
    stop_fan_img_tk = None

# ------------------------------
# REPLACE TEXT BUTTONS WITH IMAGES
# ------------------------------

# Start New Experiment => Start Experiment image
btn_new_exp = tk.Button(
    left_frame,
    image=start_experiment_img_tk,
    command=start_new_experiment,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
btn_new_exp.image = start_experiment_img_tk
btn_new_exp.pack(pady=(0, 15))

# Operation Controls label
operation_controls_label = tk.Label(
    left_frame, text="Operation Controls", font=("Arial", 14, "bold"),
    fg="white", bg="#2b2b2b"
)
operation_controls_label.pack(pady=(0,5))

# Record Background Noise
btn_bg = tk.Button(
    left_frame,
    image=rec_back_img_tk,
    command=record_background,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
btn_bg.image = rec_back_img_tk
btn_bg.pack(pady=5)

# Record Operation Noise
btn_op = tk.Button(
    left_frame,
    image=rec_oper_img_tk,
    command=record_operation,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
btn_op.image = rec_oper_img_tk
btn_op.pack(pady=5)

# Compute Noise Isolation
btn_iso = tk.Button(
    left_frame,
    image=comp_noise_img_tk,
    command=compute_noise_isolation,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
btn_iso.image = comp_noise_img_tk
btn_iso.pack(pady=5)

# Fan Controls label
fan_controls_label = tk.Label(
    left_frame, text="Fan Controls", font=("Arial", 14, "bold"),
    fg="white", bg="#2b2b2b"
)
fan_controls_label.pack(pady=(20,5))

# Fan Speed Entry (dark background, white text)
fan_speed_entry = tk.Entry(left_frame, width=10, fg="white", bg="#3a3a3a", insertbackground="white")
fan_speed_entry.pack(pady=(0,5))

# Frame to hold Set Fan Speed & Stop Fan
fan_button_frame = tk.Frame(left_frame, bg="#2b2b2b")
fan_button_frame.pack(pady=5)

# Set Fan Speed (176×161)
set_speed_button = tk.Button(
    fan_button_frame,
    image=set_fan_img_tk,
    command=set_fan_speed,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
set_speed_button.image = set_fan_img_tk
set_speed_button.pack(side=tk.LEFT, padx=5)

# Stop Fan (176×161)
stop_button = tk.Button(
    fan_button_frame,
    image=stop_fan_img_tk,
    command=stop_fan,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
stop_button.image = stop_fan_img_tk
stop_button.pack(side=tk.LEFT, padx=5)

# Fan speed status label
fan_speed_status_label = tk.Label(
    left_frame, text="Air Speed: N/A", font=("Arial", 10, "italic"),
    fg="white", bg="#2b2b2b"
)
fan_speed_status_label.pack(pady=10)

# Record Fan Speed
record_fan_speed_button = tk.Button(
    left_frame,
    image=rec_fan_speed_img_tk,
    command=toggle_record_fan_speed,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
record_fan_speed_button.image = rec_fan_speed_img_tk
record_fan_speed_button.pack(pady=5)

# Recording Timer Label
record_timer_label = tk.Label(
    left_frame, text="Recording time: 0 s", font=("Arial", 10),
    fg="white", bg="#2b2b2b"
)
record_timer_label.pack(pady=5)

# PWM Controls label
pwm_controls_label = tk.Label(
    left_frame, text="PWM Controls", font=("Arial", 14, "bold"),
    fg="white", bg="#2b2b2b"
)
pwm_controls_label.pack(pady=(20,5))

# PWM Entry
pwm_entry = tk.Entry(left_frame, width=10, fg="white", bg="#3a3a3a", insertbackground="white")
pwm_entry.pack(pady=(0,5))

# Set PWM
set_pwm_button = tk.Button(
    left_frame,
    image=set_pwm_img_tk,
    command=set_pwm_signal,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
set_pwm_button.image = set_pwm_img_tk
set_pwm_button.pack(pady=5)

# PWM reading display label
pwm_status_label = tk.Label(
    left_frame, text="PWM: N/A", font=("Arial", 10, "italic"),
    fg="white", bg="#2b2b2b"
)
pwm_status_label.pack(pady=5)

# COM Port label
com_port_label = tk.Label(
    left_frame, text="Set COM Port (e.g., COM3):", font=("Arial", 14, "bold"),
    fg="white", bg="#2b2b2b"
)
com_port_label.pack(pady=(20, 5))

com_port_entry = tk.Entry(left_frame, width=10, fg="white", bg="#3a3a3a", insertbackground="white")
com_port_entry.pack(pady=(0, 5))

# Set COM Port
set_com_port_button = tk.Button(
    left_frame,
    image=set_com_img_tk,
    command=set_com_port,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
set_com_port_button.image = set_com_img_tk
set_com_port_button.pack(pady=5)

# Graph Controls
graph_controls_label = tk.Label(
    left_frame, text="Graph Controls", font=("Arial", 14, "bold"),
    fg="white", bg="#2b2b2b"
)
graph_controls_label.pack(pady=(20,5))

ymin_label = tk.Label(left_frame, text="Y-Min:", fg="white", bg="#2b2b2b")
ymin_label.pack(pady=(0,2))
ymin_entry = tk.Entry(left_frame, width=10, fg="white", bg="#3a3a3a", insertbackground="white")
ymin_entry.pack(pady=(0,5))
ymin_entry.insert(0, "-50")

ymax_label = tk.Label(left_frame, text="Y-Max:", fg="white", bg="#2b2b2b")
ymax_label.pack(pady=(0,2))
ymax_entry = tk.Entry(left_frame, width=10, fg="white", bg="#3a3a3a", insertbackground="white")
ymax_entry.pack(pady=(0,5))
ymax_entry.insert(0, "120")

# Set Y Axis
set_y_axis_button = tk.Button(
    left_frame,
    image=set_y_axis_img_tk,
    command=set_y_axis_specific,
    bd=0, highlightthickness=0, cursor="hand2",
    bg="#2b2b2b", activebackground="#2b2b2b"
)
set_y_axis_button.image = set_y_axis_img_tk
set_y_axis_button.pack(pady=5)

# Start periodic fan speed checks
periodic_fan_check()

# Main loop
root.mainloop()
