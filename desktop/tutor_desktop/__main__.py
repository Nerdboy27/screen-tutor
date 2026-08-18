"""Entry point: ``python -m tutor_desktop`` / ``screen-tutor``."""

from __future__ import annotations

import argparse
import logging

from tutor_desktop.app import TutorOverlay
from tutor_desktop.config import DesktopConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen-Aware AI Tutor desktop client")
    parser.add_argument("--api-base-url", dest="api_base_url")
    parser.add_argument("--api-key", dest="api_key")
    parser.add_argument("--hotkey", dest="hotkey", help="e.g. '<ctrl>+<shift>+<space>'")
    parser.add_argument("--monitor", dest="monitor", type=int)
    parser.add_argument(
        "--save-config", action="store_true", help="Persist the resolved settings"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    config = DesktopConfig.load()
    for field_name in ("api_base_url", "api_key", "hotkey", "monitor"):
        value = getattr(args, field_name)
        if value is not None:
            setattr(config, field_name, value)

    if args.save_config:
        print(f"Configuration written to {config.save()}")

    TutorOverlay(config=config).run()


if __name__ == "__main__":
    main()
