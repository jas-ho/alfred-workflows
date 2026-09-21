#!/usr/bin/python3
import sys
from doorplate import action_main

action_main(sys.argv[1] if len(sys.argv) > 1 else "{}")
