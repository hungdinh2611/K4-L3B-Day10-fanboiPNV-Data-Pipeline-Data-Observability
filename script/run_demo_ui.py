from __future__ import annotations

import argparse

from demo_ui import serve


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo UI for the Day 10 data pipeline.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()
    serve(args.host, args.port, open_browser=not args.no_browser)
