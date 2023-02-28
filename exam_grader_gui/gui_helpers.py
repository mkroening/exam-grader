import os
import subprocess
import sys
from typing import Optional, Callable, Any
from collections import deque
from datetime import datetime
from pathlib import Path

from gi.repository import Gdk, Gtk

provider = Gtk.CssProvider()
provider.load_from_data(
    """
    #failable_entry.red { background: LightCoral; }
    """.encode()
)


def get_content(entry, target_type, testfn: Optional[Callable[[Any], bool]] = None):
    """
    Helper fn that queries an gtk entry and colors the entry box upon invalid content
    Returns the content cast into `desired_type`
    """
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    text = entry.get_text()
    entry.set_name("failable_entry")
    if text == "":
        entry.get_style_context().remove_class("red")
        return None
    try:
        ret = target_type(text)
        if testfn is not None:
            if not testfn(ret):
                raise ValueError
        entry.get_style_context().remove_class("red")
        return ret
    except ValueError:
        # print("Invalid entry: " + text)
        entry.get_style_context().add_class("red")
        return None


def get_content_list(entry, target_type):
    """
    Helper fn that queries an gtk entry and colors the entry box upon invalid content
    Returns the content as a list splitted at ',' and cast into `desired_type`
    """
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    text = entry.get_text()
    entry.set_name("failable_entry")
    if text == "":
        entry.get_style_context().remove_class("red")
        return None
    try:
        content_list = list(map(target_type, text.strip(",").split(",")))
        entry.get_style_context().remove_class("red")
        return content_list
    except ValueError:
        entry.get_style_context().add_class("red")
        return None


def show_about_dialog(parent):
    gladefile = Path(__file__) / "../glade/About.glade"
    builder = Gtk.Builder()
    builder.add_from_file(str(gladefile.resolve()))
    dialog = builder.get_object("about")
    dialog.set_transient_for(parent)
    dialog.run()
    dialog.destroy()


def open_file(filename):
    """
    opens a file with the default handler.
    Kudos to https://stackoverflow.com/a/17317468/6551168
    """
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


def successful_with_open_folder_dialog(parent_window, message: str, path: Path):
    dialog = Gtk.MessageDialog(
        parent_window,
        Gtk.DialogFlags.MODAL
        | Gtk.DialogFlags.DESTROY_WITH_PARENT
        | Gtk.DialogFlags.USE_HEADER_BAR,
        Gtk.MessageType.INFO,
        Gtk.ButtonsType.OK,
        message,
    )
    dialog.add_button("Open Folder", 42)
    dialog.show_all()
    response = dialog.run()
    if response == 42:
        open_file(path)
    dialog.destroy()


class ETA_calculator:
    def __init__(self, nr_elements: int, smooting_elems: int = 8):
        self.start = datetime.now()
        self.nr_elements: int = nr_elements
        self.etas: deque = deque(maxlen=smooting_elems)
        self.progress: int = 0
        self.avg_eta: Optional[int] = None
        self.smooting_elems = smooting_elems

    def update(self):
        self.progress += 1
        time_passed = datetime.now() - self.start
        eta = (self.nr_elements / self.progress - 1) * time_passed
        self.etas.append(eta.seconds)
        self.avg_eta = int(sum(self.etas) / len(self.etas)) + 1

    def get_eta_seconds(self) -> Optional[int]:
        return self.avg_eta

    def get_eta_text(self) -> str:
        if self.avg_eta is None:
            return "ETA: -"
        elif self.avg_eta < 30:
            return f"ETA: {self.avg_eta}s"
        elif self.avg_eta < 90:
            rounded_eta = int((self.avg_eta - 1) / 5 + 1) * 5
            return f"ETA: {rounded_eta}s"
        elif self.avg_eta < 60 * 15:
            minutes = int((self.avg_eta + 14) / 60)
            seconds = self.avg_eta - (minutes * 60)
            rounded_seconds = int((seconds - 1) / 15 + 1) * 15  # Round towards 15 s
            return f"ETA: {minutes}min {rounded_seconds}s"
        else:
            minutes = int(self.avg_eta / 60)
            return f"ETA: {minutes}min"
