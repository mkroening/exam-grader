from enum import Enum
from logging import error
from pathlib import Path
from typing import Callable, List

from gi.repository import Gtk

from .gui_helpers import show_about_dialog


class GuiPages(Enum):
    EXAM_SETUP = 1
    GRADING = 2


class MainWindow:
    def __init__(self):
        gladefile = Path(__file__) / "../glade/Main_Window.glade"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(gladefile.resolve()))

        self.window = self.builder.get_object("window")

        self.main_stack = self.builder.get_object("main_stack")

        self.window.show_all()
        handlers = {
            "onDestroy": Gtk.main_quit,
            "on_open_clicked": self.open,
            "on_about_clicked": self.on_about_clicked,
            "export_clicked": self.export,
            "on_main_stack_visible_child_changed": self.on_main_stack_visible_child_changed,
            "on_examdate_clicked": self.on_examdate_clicked,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")

        self.task_list = self.builder.get_object("task_list")
        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")

        self.task_list.add(AddTaskRow(self.add_task))

        self.set_visible_buttons(GuiPages.EXAM_SETUP)

        self.tasks: List[str, int] = []

    def on_main_stack_visible_child_changed(self, stack_widget, variable):
        visible_page = stack_widget.get_visible_child_name()
        if visible_page == "scan_sorter":
            self.set_visible_buttons(GuiPages.GRADING)
        elif visible_page == "barcode_generation":
            self.set_visible_buttons(GuiPages.EXAM_SETUP)
        else:
            error(f"Invalid stack page: {visible_page}")
            raise (RuntimeError(f"Invalid stack page: {visible_page}"))

    def set_visible_buttons(self, page: GuiPages):
        if page == GuiPages.EXAM_SETUP:
            self.export_button.set_visible(False)
            self.open_button.set_visible(False)
        elif page == GuiPages.GRADING:
            self.export_button.set_visible(True)
            self.open_button.set_visible(True)

    def on_about_clicked(self, _widget):
        self.help_menu_popover.popdown()
        show_about_dialog(self.window)

    def open(self, _widget):
        pass

    def on_examdate_clicked(self, widget):
        print("examdate selected")

    def export(self, _widget):
        pass

    def add_task(self, name: str, points: int):
        self.tasks.append((name, points))
        self.task_list.remove(self.task_list.get_children()[-1])
        self.task_list.add(TaskRow(len(self.tasks) - 1, name, points, self.remove_task))
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

    def remove_task(self, id: int):
        # First two items are header and seperator
        self.task_list.remove(self.task_list.get_children()[id + 2])
        self.tasks.remove(self.tasks[id])
        self.task_list.show_all()


@Gtk.Template(filename=str((Path(__file__) / "../glade/Add_Task_Row.glade").resolve()))
class AddTaskRow(Gtk.Box):
    __gtype_name__ = "add_task_row"

    taskname_entry = Gtk.Template.Child("taskname_entry")
    points_entry = Gtk.Template.Child("points_entry")
    add_button = Gtk.Template.Child("add_button")

    def __init__(self, cb: Callable[[str, int], None]):
        super(Gtk.Box, self).__init__()

        self.add_button.connect("clicked", self.add_clicked)
        self.cb = cb

    def add_clicked(self, widget):
        try:
            points = int(self.points_entry.get_text())
            self.cb(self.taskname_entry.get_text(), points)
        except ValueError:
            # TODO: mark points red
            pass


@Gtk.Template(filename=str((Path(__file__) / "../glade/Task_Row.glade").resolve()))
class TaskRow(Gtk.Box):
    __gtype_name__ = "task_row"

    taskname_label = Gtk.Template.Child("taskname_label")
    points_label = Gtk.Template.Child("points_label")
    remove_button = Gtk.Template.Child("remove_button")

    def __init__(self, id: int, name: str, points: int, cb: Callable[[int], None]):
        super(Gtk.Box, self).__init__()

        self.id = id
        self.taskname_label.set_text(name)
        self.points_label.set_text(str(points))
        self.remove_button.connect("clicked", self.remove_clicked)
        self.cb = cb

    def remove_clicked(self, widget):
        self.cb(self.id)
