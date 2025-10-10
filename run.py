#!/usr/bin/env python3
"""
GeoJSON to 3D Globe Generator
Main launcher script - delegates to src/blender_runner.py
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

# Import and run the main blender_runner
from blender_runner import main

if __name__ == '__main__':
    sys.exit(main())
