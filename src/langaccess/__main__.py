# -*- coding: utf-8 -*-
"""`python -m langaccess` runs the same command line as the `langaccess` script.

The console script is what the documentation gives, and on Windows it lands in a virtual
environment's Scripts directory, which is not on PATH unless the environment is activated. A first
run there fails on a missing command rather than on anything about the package, so the module form
is carried as well and dispatches to exactly the same entry point.
"""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())
