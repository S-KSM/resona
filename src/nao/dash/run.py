"""`nao-dash` entrypoint — wraps `streamlit run` so users don't need to know
the path to app.py."""
from __future__ import annotations

import pathlib
import sys

from streamlit.web import cli as stcli


def main() -> None:
    app_path = pathlib.Path(__file__).parent / "app.py"
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
