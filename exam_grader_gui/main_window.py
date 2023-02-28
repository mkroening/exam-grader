import random
from dataclasses import dataclass
from enum import Enum
from logging import error
from pathlib import Path
from typing import Callable, List, Dict
from gi.repository import Gtk
from matplotlib.figure import Figure
from numpy import pi, linspace
import matplotlib.cm as cm
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas

from .gui_helpers import get_content, show_about_dialog


@dataclass
class ExamTask:
    name: str
    max_points: int
    id: int


class PointTable:
    def __init__(
        self, passing: float, step: float, max_pts: float, min_step: float = 0.5
    ):
        self.labels = [
            "5.0",
            "4.0",
            "3.7",
            "3.3",
            "3.0",
            "2.7",
            "2.3",
            "2.0",
            "1.7",
            "1.3",
            "1.0",
        ]
        self.points_min = [0.0]
        pm = passing
        for i in range(len(self.labels) - 1):
            self.points_min.append(pm)
            pm += step

        pm = passing - min_step
        self.points_max = [pm]
        for i in range(len(self.labels) - 2):
            pm += step
            self.points_max.append(pm)
        self.points_max.append(max_pts)

    def grade(self, points: float) -> str:
        for i, l in enumerate(self.labels):
            if points < self.points_min[i]:
                return self.labels[i - 1]
        return self.labels[-1]


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
            "on_examdate_selected": self.on_examdate_clicked,
            "on_gradetable_value_changed": self.update_grade_table,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")

        self.task_list = self.builder.get_object("task_list")
        self.task_list.add(AddTaskRow(self.add_task))
        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")
        self.grading_table = self.builder.get_object("grading_tabl")
        self.task_label_box = self.builder.get_object("task_label_box")
        self.histogram_area = self.builder.get_object("histogram_area")

        self.point_table = PointTable(10, 5, 100)

        mplfigure = Figure(figsize=(10, 2), dpi=100)
        self.histogramax = mplfigure.add_subplot(111)
        self.histogrambars = self.histogramax.bar(
            self.point_table.labels,
            [3.0] * len(self.point_table.labels),
            width=0.5,
        )
        self.histogramax.plot()
        self.canvas = FigureCanvas(mplfigure)
        self.canvas.set_size_request(450, 200)
        self.histogram_area.add_with_viewport(self.canvas)
        self.histogram_area.show_all()

        self.grading_rows = []
        self.tasks: List[ExamTask] = []
        self.add_task("Exampletask", 10)

        self.grading_rows = [
            GradingRow(
                "12345",
                "Peter",
                "Pan",
                self.tasks,
                self.grade_calculation,
                self.update_histogram,
            ),
            GradingRow(
                "12345",
                "Peter",
                "Pan",
                self.tasks,
                self.grade_calculation,
                self.update_histogram,
            ),
        ]
        for row in self.grading_rows:
            self.grading_table.add(row)
        self.grading_table.show_all()

        self.update_grade_table(None)

    def draw_histogram(self):
        for i, b in enumerate(self.histogrambars):
            b.set_height(self.histogram[self.point_table.labels[i]])
        self.histogramax.relim()
        self.histogramax.autoscale_view()
        self.canvas.draw()
        self.canvas.flush_events()

    def update_grade_table(self, widget):
        passing_spin = self.builder.get_object("passing_spin_but")
        passing_pts = passing_spin.get_value()
        stepsize_spin_but = self.builder.get_object("stepsize_spin_but")
        stepsize = stepsize_spin_but.get_value()
        self.point_table = PointTable(passing_pts, stepsize, 100, 0.5)

        for i, grade in enumerate(self.point_table.labels):
            label_from = self.builder.get_object(f"{grade}_from")
            label_from.set_text(f"{self.point_table.points_min[i]}")
            label_to = self.builder.get_object(f"{grade}_to")
            label_to.set_text(f"{self.point_table.points_max[i]}")

        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.grading_table.show_all()

    def update_histogram(self, widget):
        self.histogram = self.generate_histogram()
        for grade in self.point_table.labels:
            label_count = self.builder.get_object(f"{grade}_count")
            label_count.set_text(f"{self.histogram[grade]}")
        self.builder.get_object("point_table").show_all()
        self.draw_histogram()

    def generate_histogram(self) -> Dict[str, int]:
        hist = {}
        for label in self.point_table.labels:
            hist[label] = 0
        for row in self.grading_rows:
            try:
                hist[row.grade_final] += 1
            except KeyError:
                pass
        return hist

    def grade_calculation(self, points: float) -> str:
        return self.point_table.grade(points)

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
            label = Gtk.Label(f"T {i}:\n{t.name[0:10]}")
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
        self,
        student_id: str,
        first_name: str,
        surname: str,
        tasks: [ExamTask],
        grade_calculation: Callable[[MainWindow, float], str],
        update_callback: Callable[[MainWindow], None],
    ):
        super(Gtk.Box, self).__init__()

        self.id = id
        self.student_id_label.set_text(student_id)
        self.first_name_label.set_text(first_name)
        self.surname_label.set_text(surname)
        self.grade_calculation = grade_calculation
        self.update_callback = update_callback

        self.additional_points_entry.connect("changed", self.on_update)

        self.point_entries = {}

        self.points = 0.0
        self.points_final = 0.0
        self.grade = ""
        self.grade_final = ""

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
        self.on_update(None)

    def on_update(self, widget):
        sum = 0.0
        for entry in self.point_entries.items():

            def validate_maxpoints(points):
                return points <= entry[1][0].max_points

            p = get_content(entry[1][1], float, validate_maxpoints)
            if p is not None:
                sum += p
        self.points = sum
        self.total_points_label.set_text(str(self.points))
        self.grade = self.grade_calculation(sum)
        self.grade_label.set_text(str(self.grade))
        ap = get_content(self.additional_points_entry, int)
        if ap is not None:
            sum += ap
        self.points_final = sum
        self.total_points_final_label.set_text(str(self.points_final))
        self.grade_final = self.grade_calculation(sum)
        self.grade_final_label.set_text(str(self.grade_final))
        self.update_callback(self)

    def get_task_points(tasknr: int) -> float:
        return get_content(self.point_entries[i][1], float, validate_maxpoints)
