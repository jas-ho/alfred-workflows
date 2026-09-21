#!/usr/bin/python3
import sys
from doorplate import filter_main

filter_main("close", sys.argv[1] if len(sys.argv) > 1 else "")
