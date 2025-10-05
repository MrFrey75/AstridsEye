
"""
Launcher for AstridsEye GUI.
Keeps src/app.py as a minimal entry point for launching the GUI.
"""

import sys
import os
import tkinter as tk

# Import the GUI module with fallbacks
try:
    from .gui import AstridsEyeGUI
except Exception:
    this_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(this_file)
    project_root = os.path.dirname(src_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from gui import AstridsEyeGUI
    except Exception:
        from src.gui import AstridsEyeGUI

if __name__ == '__main__':
    class AstridsEyeGUIWithErrorRaw(AstridsEyeGUI):
        def show_error_in_raw(self, error_msg):
            """
            Display error message in the raw data view area.
            """
            if hasattr(self, 'raw_text'):
                self.raw_text.config(state='normal')
                self.raw_text.delete(1.0, 'end')
                self.raw_text.insert('end', error_msg)
                self.raw_text.config(state='disabled')

        def run_with_error_hook(self):
            try:
                self.run()
            except Exception as e:
                self.show_error_in_raw(f"Error: {str(e)}")

    root = tk.Tk()
    app = AstridsEyeGUIWithErrorRaw(root)
    app.run_with_error_hook()

