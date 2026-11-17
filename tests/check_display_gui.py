"""Compatibility entry point for the segment display and persistence checks."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name('check_segment_gui.py')), run_name='__main__')
