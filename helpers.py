# helpers.py
import tkinter as tk

class SerialDebugWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Serial Debug Monitor")
        self.geometry("600x400")
        # Create a text widget to display serial data
        self.text_area = tk.Text(self, state='disabled')
        self.text_area.pack(expand=True, fill='both')
    
    def append_data(self, data: str):
        """Append new serial data to the display."""
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, data + "\n")
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)

def show_serial_debug_window(existing_window=None):
    """
    Create and show the serial debug window.
    If a window already exists, bring it to the front.
    """
    if existing_window is None or not existing_window.winfo_exists():
        existing_window = SerialDebugWindow()
    else:
        existing_window.lift()
    return existing_window
