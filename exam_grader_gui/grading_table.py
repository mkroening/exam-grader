from gi.repository import Gtk
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional, Tuple
from .exam import ExamTask

from .gui_helpers import get_content


def round_half_points(f: float) -> float:
    return int((f + 0.25) / 0.5) * 0.5


@Gtk.Template(filename=str((Path(__file__) / "../glade/Grading_Row.glade").resolve()))
class GradingRow(Gtk.Box):
    __gtype_name__ = "grading_row"

    student_id_label = Gtk.Template.Child("student_id_label")
    first_name_label = Gtk.Template.Child("first_name_label")
    surname_label = Gtk.Template.Child("surname_label")
    trials_label = Gtk.Template.Child("trials_label")
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
        trials: int,
        tasks: [ExamTask],
        grade_calculation: Callable[["MainWindow", Tuple[float, bool]], str],
        update_callback: Callable[["MainWindow"], None],
        points: Optional[List[float]] = None,
    ):
        super(Gtk.Box, self).__init__()

        self.stud_id = student_id
        self.student_id_label.set_text(student_id)
        self.first_name = first_name
        self.first_name_label.set_text(self.first_name)
        self.surname = surname
        self.surname_label.set_text(self.surname)
        self.grade_calculation = grade_calculation
        self.update_callback = update_callback

        self.trials = trials
        self.trials_label.set_text(str(self.trials))
        if trials > 2:
            self.trials_label.get_style_context().add_class("warning")

        self.point_entries = {}

        self.additional_points_entry.connect("changed", self.on_update)
        if points is not None:
            self.additional_points_entry.set_text(str(points[-1]))

        self.points = 0.0
        self.points_final = 0.0
        self.grade = "5.0"
        self.grade_final = "5.0"

        if points is not None:
            assert len(points) == len(tasks) + 1

        for i, t in enumerate(tasks):
            taskpoint_entry = self.new_entry()
            if points is not None:
                taskpoint_entry.set_text(str(points[i]))
                taskpoint_entry.set_progress_fraction(points[i] / tasks[i].max_points)
            self.point_entries[i] = (t, taskpoint_entry)
            self.task_point_area.add(taskpoint_entry)
        self.task_point_area.show_all()

    def new_entry(self) -> Gtk.Entry:
        taskpoint_entry = Gtk.Entry()
        taskpoint_entry.set_size_request(90, -1)
        taskpoint_entry.set_placeholder_text("0.0")
        taskpoint_entry.set_alignment(0.5)
        taskpoint_entry.set_width_chars(3)
        taskpoint_entry.connect("changed", self.on_update)
        taskpoint_entry.get_style_context().add_class("flat")
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
                entry[1][1].set_progress_fraction(p / entry[1][0].max_points)
                sum += p
        self.points = round_half_points(sum)
        self.total_points_label.set_text(str(self.points))
        self.grade, passed = self.grade_calculation(sum)
        if not passed:
            self.grade_label.get_style_context().add_class("error")
        else:
            self.grade_label.get_style_context().remove_class("error")
        self.grade_label.set_text(str(self.grade))
        ap = get_content(self.additional_points_entry, float)
        if ap is not None:
            sum += ap
        self.points_final = round_half_points(sum)
        self.total_points_final_label.set_text(str(self.points_final))
        self.grade_final, passed = self.grade_calculation(sum)
        if not passed:
            self.grade_final_label.get_style_context().add_class("error")
            if self.trials > 2:
                self.first_name_label.get_style_context().add_class("error")
                self.surname_label.get_style_context().add_class("error")
        else:
            self.grade_final_label.get_style_context().remove_class("error")
            self.first_name_label.get_style_context().remove_class("error")
            self.surname_label.get_style_context().remove_class("error")
        self.grade_final_label.set_text(str(self.grade_final))
        self.update_callback(self)

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "StudentID": self.student_id_label.get_text(),
            "First_Name": self.first_name_label.get_text(),
            "Surname": self.surname_label.get_text(),
            "Attempt": self.trials,
        }
        taskpts = {}
        for entry in self.point_entries.items():
            try:
                taskpts[str(entry[1][0].id)] = float(entry[1][1].get_text())
            except ValueError:
                taskpts[str(entry[1][0].id)] = 0.0
        try:
            taskpts["Additional_Points"] = float(
                self.additional_points_entry.get_text()
            )
        except ValueError:
            taskpts["Additional_Points"] = 0.0
        d["Tasks"] = taskpts
        return d

    def get_task_points(self, tasknr: int) -> float:
        try:
            return float(self.point_entries[tasknr][1].get_text())
        except ValueError:
            return 0.0

    def get_additional_points(self) -> float:
        try:
            return float(self.additional_points_entry.get_text())
        except ValueError:
            return 0.0
