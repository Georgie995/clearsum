"""The packaged app's front door.

Double-clicked: opens the ClearSum window.
Started by the engine as `ClearSum.exe -m manifest_doctor …` ("tool mode"): behaves exactly
like `python -m manifest_doctor …`. A packaged app has no separate Python to start its tools
with, so it starts a copy of itself instead. Only the app's own tools can be started this way.
"""

import runpy
import sys

TOOLS = {"manifest_doctor", "delivery_ops_hub"}


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "-m":
        module = sys.argv[2]
        if module not in TOOLS:
            sys.exit(f"ClearSum: {module} isn't one of the app's tools")
        sys.argv = [module, *sys.argv[3:]]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from clearsum.selftest import run
        run(sys.argv[2])
        return
    from clearsum.app import main as open_app
    open_app()


if __name__ == "__main__":
    main()
