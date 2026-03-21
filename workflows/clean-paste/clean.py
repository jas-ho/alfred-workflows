#!/usr/bin/env python3
import subprocess

from clean_core import clean

def main():
    text = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
    print(clean(text))


if __name__ == "__main__":
    main()
