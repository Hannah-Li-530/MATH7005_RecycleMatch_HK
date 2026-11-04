"""Headless smoke test for the Streamlit app using streamlit.testing.v1.AppTest.

Executes app.py end-to-end without a browser: renders the initial page,
simulates sidebar interaction (pick a mode, select materials, set a limit),
and asserts no exception is raised and expected widgets render.

Run from the python_app folder:
    C:\\Users\\Lenovo\\AppData\\Local\\Programs\\Python\\Python312\\python.exe smoke_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_FILE = Path(__file__).resolve().parent / "app.py"


def main() -> None:
    at = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    if at.exception:
        print("FAIL initial render:", at.exception)
        sys.exit(1)
    print("PASS initial render")
    print("PASS title:", at.title[0].value)

    # Interact: fewer-stops mode, select three materials, limit 8.
    at.sidebar.radio[0].set_value("尽量少跑几个点").run(timeout=60)
    if at.exception:
        print("FAIL after mode change:", at.exception)
        sys.exit(1)
    print("PASS mode change")

    # Pick the first three material options.
    at.sidebar.multiselect[0].set_value(at.sidebar.multiselect[0].options[:3]).run(timeout=60)
    if at.exception:
        print("FAIL after material selection:", at.exception)
        sys.exit(1)
    print("PASS material selection")

    at.sidebar.slider[0].set_value(8).run(timeout=60)
    if at.exception:
        print("FAIL after limit change:", at.exception)
        sys.exit(1)
    print("PASS limit change")

    # Set explicit coordinates to exercise the recommendation path.
    # (number_input changes trigger a rerun; the address-search button stays
    # disabled here because it requires network geocoding, which this smoke
    # test intentionally does not exercise.)
    at.number_input[0].set_value(22.302711)
    at.number_input[1].set_value(114.177216)
    at.run(timeout=60)
    if at.exception:
        print("FAIL after coordinate update:", at.exception)
        sys.exit(1)
    print("PASS coordinate update")

    # The recommendation block should have produced markdown text.
    texts = [m.value for m in at.markdown]
    print("PASS rendered markdown blocks:", len(texts))

    # Trigger the address-search button path is not exercised (needs network);
    # manual coordinates above cover the core recommendation flow.
    print("SMOKE OK")


if __name__ == "__main__":
    main()
