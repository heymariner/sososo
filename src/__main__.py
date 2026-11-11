"""Allow ``python -m src`` to run the HeyMariner CLI."""

from src.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
