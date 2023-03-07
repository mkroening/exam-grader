import random
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gio
from logging import getLogger, DEBUG
from pathlib import Path

Gio.resources_register(
    Gio.Resource.load(str((Path(__file__) / "../../ui.gresource").resolve()))
)

from .main_window import MainWindow  # noqa: E402,F401


logger = getLogger()
logger.setLevel(DEBUG)
random.seed()
