import sys

from agentic_tutorial.education.__main__ import main

raise SystemExit(main(["approval", *sys.argv[1:]]))
