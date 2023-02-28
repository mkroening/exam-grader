import random
from dataclasses import dataclass
from enum import Enum
from logging import error
from pathlib import Path
from typing import Callable, List

from gi.repository import Gtk

from .gui_helpers import get_content, show_about_dialog


class GuiPages(Enum):
    EXAM_SETUP = 1
    GRADING = 2


@dataclass
class ExamTask:
    name: str
    max_points: int
    id: int


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
            "on_examdate_selected": self.on_examdate_clicked,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")

        self.task_list = self.builder.get_object("task_list")
        self.task_list.add(AddTaskRow(self.add_task))
        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")
        self.grading_table = self.builder.get_object("grading_tabl")
        self.task_label_box = self.builder.get_object("task_label_box")

        self.grading_rows = []
        self.tasks: List[ExamTask] = []
        self.add_task("Exampletask", 10)

        self.grading_rows = [
            GradingRow("12345", "Peter", "Pan", self.tasks),
            GradingRow("12345", "Peter", "Pan", self.tasks),
        ]
        for row in self.grading_rows:
            self.grading_table.add(row)
        self.grading_table.show_all()

        self.set_visible_buttons(GuiPages.EXAM_SETUP)

    def on_main_stack_visible_child_changed(self, stack_widget, variable):
        return
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
        id = random.randint(1, 100000000)
        self.tasks.append(ExamTask(name, points, id))
        self.task_list.remove(self.task_list.get_children()[-1])
        self.task_list.add(TaskRow(len(self.tasks) - 1, name, points, self.remove_task))
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.grading_table.show_all()

        self.rebuild_gradingtable_header()

    def remove_task(self, id: int):
        # First two items are header and seperator
        self.task_list.remove(self.task_list.get_children()[id + 2])
        self.tasks.remove(self.tasks[id])
        self.task_list.show_all()

        for row in self.grading_rows:
            row.update_entries(self.tasks)
        # self.grading_table.show_all()
        self.rebuild_gradingtable_header()

    def rebuild_gradingtable_header(self):
        for child in self.task_label_box.get_children():
            self.task_label_box.remove(child)
        for i, t in enumerate(self.tasks):
            label = Gtk.Label(f"T{i}:\n{t.name[0:10]}")
            label.set_size_request(90, -1)
            label.set_justify(Gtk.Justification.CENTER)
            self.task_label_box.add(label)
        self.task_label_box.show_all()

@Gtk.Template(filename=str((Path(__file__) / "../glade/Add_Task_Row.glade").resolve()))
class AddTaskRow(Gtk.Box):
    __gtype_name__ = "add_task_row"

    taskname_entry = Gtk.Template.Child("taskname_entry")
    points_entry = Gtk.Template.Child("points_entry")
    add_button = Gtk.Template.Child("add_button")

    def __init__(self, cb: Callable[[str, int], None]):
        super(Gtk.Box, self).__init__()

        self.add_button.connect("clicked", self.add_clicked)
        self.points_entry.connect("changed", self.on_update)
        self.cb = cb

    def on_update(self, widget):
        self.add_button.set_sensitive(get_content(widget, int) is not None)

    def add_clicked(self, widget):
        points = get_content(self.points_entry, int)
        if points is not None:
            self.cb(self.taskname_entry.get_text(), points)


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


@Gtk.Template(filename=str((Path(__file__) / "../glade/Grading_Row.glade").resolve()))
class GradingRow(Gtk.Box):
    __gtype_name__ = "grading_row"

    student_id_label = Gtk.Template.Child("student_id_label")
    first_name_label = Gtk.Template.Child("first_name_label")
    surname_label = Gtk.Template.Child("surname_label")
    total_points_label = Gtk.Template.Child("total_points_label")
    total_points_final_label = Gtk.Template.Child("total_points_final_label")
    grade_label = Gtk.Template.Child("grade_label")
    grade_final_label = Gtk.Template.Child("grade_final_label")
    task_point_area = Gtk.Template.Child("task_points")

    additional_points_entry = Gtk.Template.Child("additional_points_entry")

    def __init__(
        self, student_id: str, first_name: str, surname: str, tasks: [ExamTask]
    ):
        super(Gtk.Box, self).__init__()

        self.id = id
        self.student_id_label.set_text(student_id)
        self.first_name_label.set_text(first_name)
        self.surname_label.set_text(surname)

        self.additional_points_entry.connect("changed", self.on_update)

        self.point_entries = {}

        for i in range(len(tasks)):
            taskpoint_entry = self.new_entry()
            self.point_entries[i] = (tasks[i], taskpoint_entry)
            self.task_point_area.add(taskpoint_entry)

    def new_entry(self) -> Gtk.Entry:
        taskpoint_entry = Gtk.Entry()
        taskpoint_entry.set_size_request(90, -1)
        taskpoint_entry.set_placeholder_text("0")
        taskpoint_entry.set_alignment(0.5)
        taskpoint_entry.set_width_chars(3)
        taskpoint_entry.connect("changed", self.on_update)
        return taskpoint_entry

    def update_entries(self, new_tasklist: List[ExamTask]):
        for child in self.task_point_area.get_children():
            self.task_point_area.remove(child)
        tmp_point_entries = self.point_entries
        self.point_entries = {}
        for i in range(len(new_tasklist)):
            old_item = list(
                filter(
                    lambda t: t[1][0].id == new_tasklist[i].id,
                    tmp_point_entries.items(),
                )
            )
            assert len(old_item) <= 1
            if len(old_item) == 0:
                self.point_entries[i] = (new_tasklist[i], self.new_entry())
            else:
                self.point_entries[i] = old_item[0][1]
        for e in self.point_entries.items():
            self.task_point_area.add(e[1][1])
        self.show_all()

    def on_update(self, widget):
        sum = 0
        for entry in self.point_entries.items():
            def validate_maxpoints(points):
                return points <= entry[1][0].max_points

            p = get_content(entry[1][1], int, validate_maxpoints)
            if p is not None:
                sum += p
        self.total_points_label.set_text(str(sum))
        ap = get_content(self.additional_points_entry, int)
        if ap is not None:
            sum += ap
        self.total_points_final_label.set_text(str(sum))
