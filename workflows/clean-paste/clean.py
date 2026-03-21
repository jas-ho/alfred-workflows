#!/usr/bin/env python3
import subprocess

from clean_core import clean

text = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
print(clean(text))
