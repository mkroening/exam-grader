import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from gi.repository import Gdk, Gio, Gtk


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
    builder = Gtk.Builder.new_from_resource("/exam-grader/About.ui")
    dialog = builder.get_object("about")
    dialog.set_transient_for(parent)
    logo = Gdk.Texture.new_from_resource("/exam-grader/assets/exam.svg")
    dialog.set_logo(logo)
    dialog.present()


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
    dialog = Gtk.AlertDialog()
    dialog.set_message(message)
    dialog.set_buttons(["Open Folder", "Ok"])
    dialog.set_cancel_button(1)
    dialog.set_default_button(1)
    dialog.choose(parent_window, None, perform_open_folder, None, path)


def perform_open_folder(source_obj, async_res, error, path):
    result = source_obj.choose_finish(async_res)
    if result == 0:
        open_file(path)


def create_file_dialog(
    parent,
    title: str,
    lastpath: Optional[Tuple[str, Gio.File, Path]],
    filters: List[Tuple[str, str]] = [
        ("Exam Grading Files", "*.examgrades"),
        ("All Files", "*"),
    ],
) -> Gtk.FileDialog:
    file_choose_dialog = Gtk.FileDialog()
    file_choose_dialog.set_title(title)

    file_filters = Gio.ListStore.new(Gtk.FileFilter)
    for name, pattern in filters:
        filter = Gtk.FileFilter()
        filter.set_name(name)
        filter.add_pattern(pattern)
        file_filters.append(filter)
    file_choose_dialog.set_filters(file_filters)
    file_choose_dialog.set_default_filter(file_filters[0])

    if isinstance(lastpath, Gio.File):
        file_choose_dialog.set_initial_folder(lastpath)
    elif isinstance(lastpath, str):
        file_choose_dialog.set_initial_folder(Gio.File.new_for_path(lastpath))
    elif isinstance(lastpath, Path):
        if not lastpath.is_dir():
            lastpath = lastpath.parent
        file_choose_dialog.set_initial_folder(Gio.File.new_for_path(str(lastpath)))

    return file_choose_dialog


def clear_container(container, skip: int = 0):
    current_obj = container.get_first_child()
    for _ in range(skip):
        current_obj = current_obj.get_next_sibling()

    while current_obj is not None:
        next_obj = current_obj.get_next_sibling()
        container.remove(current_obj)
        current_obj = next_obj
