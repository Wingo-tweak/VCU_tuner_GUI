#!/usr/bin/env python3
import sys

from vcu_tuner.bootstrap import ensure_runtime_dependencies

if __name__ == "__main__":
    # Best effort: failure only disables optional in-window drag and drop.
    ensure_runtime_dependencies()
    from vcu_tuner.gui import main

    main(sys.argv[1] if len(sys.argv) > 1 else None)
