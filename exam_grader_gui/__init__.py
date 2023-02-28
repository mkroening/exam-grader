import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from logging import getLogger, DEBUG

from .main_window import MainWindow  # noqa: E402,F401


logger = getLogger()
logger.setLevel(DEBUG)
