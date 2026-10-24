import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def configure_logging(directory: Path, verbose: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "tachie.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler = RotatingFileHandler(path, maxBytes=4 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    root.addHandler(file_handler)
    if sys.stderr is not None:
        console = RichHandler(rich_tracebacks=True, show_path=False, markup=False)
        console.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(console)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    return path
