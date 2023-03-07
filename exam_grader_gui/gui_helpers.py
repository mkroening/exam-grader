import os
import subprocess
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from gi.repository import Gdk, Gtk


def get_content(
    entry,
    target_type,
    testfn: Optional[Callable[[Any], bool]] = None,
    default_val: Any = None,
):
    """
    Helper fn that queries an gtk entry and colors the entry box upon invalid content
    Returns the content cast into `desired_type`
    """

    text = entry.get_text()
    entry.set_name("failable_entry")
    if text == "":
        entry.get_style_context().remove_class("red")
        return default_val
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
        return default_val


def get_content_list(entry, target_type):
    """
    Helper fn that queries an gtk entry and colors the entry box upon invalid content
    Returns the content as a list splitted at ',' and cast into `desired_type`
    """

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
    builder = Gtk.Builder.new_from_resource("/exam-grader/About.glade")
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
