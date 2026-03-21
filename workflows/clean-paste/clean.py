#!/usr/bin/env python3
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from clean_core import clean

def main():
    text = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
    print(clean(text))


if __name__ == "__main__":
    main()
