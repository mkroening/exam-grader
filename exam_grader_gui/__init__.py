import random

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from logging import DEBUG, getLogger
from pathlib import Path

from gi.repository import Gdk, Gio, Gtk

Gio.resources_register(
    Gio.Resource.load(str((Path(__file__) / "../../ui.gresource").resolve()))
)

from .main_window import MainWindow  # noqa: E402,F401


provider = Gtk.CssProvider()
provider.load_from_resource("/exam-grader/assets/style.css")
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

logger = getLogger()
logger.setLevel(DEBUG)
random.seed()
