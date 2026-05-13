"""Entry point to run the UMU Advanced web application."""

from __future__ import annotations

import os
import sys

# Allow running directly: python src/web/run.py
if __name__ == "__main__" and __package__ is None:
    _root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from web.app import app
else:
    from .app import app


def main() -> None:
    """Run the UMU Advanced web application.

    NOTE: This uses Flask's built-in development server.
    For production deployment, use a WSGI server such as gunicorn:
        gunicorn web.app:app
    """
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
