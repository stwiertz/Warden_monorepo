"""Shared pytest config — puts apps/tooling on sys.path so tests can import tools.*"""

import os
import sys

_TOOLING_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _TOOLING_ROOT not in sys.path:
    sys.path.insert(0, _TOOLING_ROOT)
