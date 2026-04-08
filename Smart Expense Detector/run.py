"""
run.py
------
Cross-platform entry point for running the Smart Expense Leak Detector API.
Wraps uvicorn with the correct multiprocessing guard for Windows + Python 3.14.

Usage:
    python run.py
"""

import multiprocessing
import uvicorn

if __name__ == "__main__":
    # Required on Windows when using multiprocessing (e.g., --reload flag)
    multiprocessing.freeze_support()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # Auto-reloads on file changes during development
        reload_dirs=["."],    # Watch the current directory
    )
