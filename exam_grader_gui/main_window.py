import random
import json
import csv
from dataclasses import dataclass
from enum import Enum
from logging import error
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
from gi.repository import Gtk, Gdk
from matplotlib.figure import Figure
from numpy import pi, linspace
import matplotlib.cm as cm
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas

from .gui_helpers import get_content, show_about_dialog
from .csv_import import CsvImportDialog


@dataclass
class ExamTask:
    name: str
    max_points: int
    id: int

    def as_dict(self) -> Dict[str, Any]:
        return {"Name": self.name, "Max_Points": self.max_points, "ID": self.id}


class PointTable:
    def __init__(
        self, passing: float, step: float, max_pts: float, min_step: float = 0.5
    ):
        self.passing = passing
        self.step = step
        self.points_maximum = max_pts
        self.min_step = min_step

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

    def grade(self, points: float) -> Tuple[str, bool]:
        '''
        Returns the grade, and wether it passes the exam
        '''
        for i, l in enumerate(self.labels):
            if points < self.points_min[i]:
                return (self.labels[i - 1], i > 1)
        return (self.labels[-1], True)

    def as_dict(self) -> Dict[str, float]:
        return {
            "passing": self.passing,
            "step": self.step,
            "max_points": self.points_maximum,
            "min_step": self.min_step,
        }


class MainWindow:
    def __init__(self):
        gladefile = Path(__file__) / "../glade/Main_Window.glade"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(gladefile.resolve()))

        self.window = self.builder.get_object("window")

        self.main_stack = self.builder.get_object("main_stack")

        provider = Gtk.CssProvider()
        provider.load_from_data(
            """
            #failable_entry.red {
                background: @error_color;
            }
            progress {
                border-bottom-color: @success_color;
                margin-left: 0;
                margin-right: 0;
                margin-bottom: -1px
            }
            """.encode()
        )
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        handlers = {
            "onDestroy": Gtk.main_quit,
            "on_about_clicked": self.on_about_clicked,
            "export_clicked": self.export,
            "on_examname_changed": self.on_examname_changed,
            "on_examdate_selected": self.on_examdate_clicked,
            "on_gradetable_value_changed": self.update_grade_table,
            "on_csv_import_clicked": self.csv_import,
            "on_main_stack_visible_child_changed": self.main_visible_child_changed,
            "on_save_clicked": self.save,
            "on_open_clicked": self.open,
            "on_new_clicked": self.clear,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")
        self.examname_entry = self.builder.get_object("examname_entry")
        self.task_list = self.builder.get_object("task_list")
        self.task_list.add(AddTaskRow(self.add_task))
        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")
        self.grading_table = self.builder.get_object("grading_tabl")
        self.task_label_box = self.builder.get_object("task_label_box")
        self.histogram_area = self.builder.get_object("histogram_area")

        self.modified = False
        self.block_histogram_update = False
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
        self.update_histogram(None, False)

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

        self.update_grade_table(None, False)
        self.modified = False

        self.window.show_all()

    def main_visible_child_changed(self, widget, data):
        if self.main_stack.get_visible_child_name() == "setup_page":
            self.draw_histogram()
        else:
            self.block_histogram_update = True

    def draw_histogram(self):
        if self.block_histogram_update:
            return
        for i, b in enumerate(self.histogrambars):
            b.set_height(self.histogram[self.point_table.labels[i]])
        self.histogramax.relim()
        self.histogramax.autoscale_view()
        self.canvas.draw()
        self.canvas.flush_events()

    def update_grade_table(self, widget, was_modified: bool = True):
        if was_modified:
            self.modified = True
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

        self.block_histogram_update = True
        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.block_histogram_update = False
        self.draw_histogram()

    def update_histogram(self, widget, was_modified: bool = True):
        if was_modified:
            self.modified = True
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

    def on_examname_changed(self, widget):
        self.modified = True

    def on_examdate_clicked(self, widget):
        # TODO:
        self.modified = True
        date = widget.get_date()
        self.examdate = f"{date.year}-{date.month}-{date.day}"
        self.builder.get_object("examdate_button_label").set_text(self.examdate)
        self.builder.get_object("examdate_button").get_popover().popdown()
        print("examdate selected")

    def export(self, _widget):
        pass

    def add_task(self, name: str, points: int, id: Optional[int] = None):
        self.modified = True
        if id is None:
            id = random.randint(1, 100000000)
        self.tasks.append(ExamTask(name, points, id))
        self.task_list.remove(self.task_list.get_children()[-1])
        self.task_list.add(TaskRow(len(self.tasks) - 1, name, points, self.remove_task))
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        self.block_histogram_update = True
        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.block_histogram_update = False
        self.draw_histogram()
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

    def csv_import(self, widget):
        dialog = CsvImportDialog(self.window)
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            if self.modified:
                warn_dialog = Gtk.MessageDialog(
                    self.window,
                    Gtk.DialogFlags.MODAL
                    | Gtk.DialogFlags.DESTROY_WITH_PARENT
                    | Gtk.DialogFlags.USE_HEADER_BAR,
                    type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK_CANCEL,
                    message_format="Overwrite existing data?",
                )
                warn_dialog.format_secondary_text("All changes so far will be lost")
                # TODO: Doesn't work
                # warn_dialog.get_widget_for_response(
                #     response_id=Gtk.ResponseType.OK
                # ).get_style_context().add_class("destructive_action")
                response = warn_dialog.run()
                warn_dialog.destroy()
                if response != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return

            self.clear_grading_rows()

            with dialog.csv.open(newline="") as csv_f:
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=dialog.csv_dialect)
                stud_id_col = reader.fieldnames[dialog.stud_id_combo.get_active()]
                first_name_col = reader.fieldnames[dialog.first_name_combo.get_active()]
                surname_col = reader.fieldnames[dialog.surname_combo.get_active()]
                # trials_col = reader.fieldnames[dialog.trial_nr_combo.get_active()]
                for row in reader:
                    stud_id = row[stud_id_col]
                    first_name = row[first_name_col]
                    surname = row[surname_col]
                    # trials = row[trials_col]

                    self.grading_rows.append(
                        GradingRow(
                            stud_id,
                            first_name,
                            surname,
                            self.tasks,
                            self.grade_calculation,
                            self.update_histogram,
                        )
                    )
            self.grading_rows = list(sorted(self.grading_rows, key=lambda r: r.stud_id))
            for row in self.grading_rows:
                self.grading_table.add(row)
            self.modified = True

        dialog.destroy()

    def clear_grading_rows(self):
        self.grading_rows.clear()
        for child in self.grading_table.get_children()[2:]:
            self.grading_table.remove(child)

    def clear_tasks(self, rebuild_gradingtable: bool = False):
        # First two items are header and seperator
        for t in self.task_list.get_children()[2:]:
            self.task_list.remove(t)
        self.tasks.clear()
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        if rebuild_gradingtable:
            for row in self.grading_rows:
                row.update_entries(self.tasks)

        self.rebuild_gradingtable_header()

    def save(self, widget):
        file_choose_dialog = Gtk.FileChooserDialog(
            "Save File",
            self.window,
            Gtk.FileChooserAction.SAVE,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )
        exam_file_filter = Gtk.FileFilter()
        exam_file_filter.set_name("Exam Grading Files")
        exam_file_filter.add_pattern("*.examgrades")
        file_choose_dialog.add_filter(exam_file_filter)
        all_files_filter = Gtk.FileFilter()
        all_files_filter.set_name("All Files")
        all_files_filter.add_pattern("*")
        examname = self.examname_entry.get_text()
        file_choose_dialog.set_current_name(f"{examname}.examgrades")

        file_choose_dialog.get_widget_for_response(
            Gtk.ResponseType.OK
        ).get_style_context().add_class("suggested-action")

        response = file_choose_dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = Path(file_choose_dialog.get_filename())
            file_choose_dialog.destroy()

            if filepath.exists():
                warn_dialog = Gtk.MessageDialog(
                    self.window,
                    Gtk.DialogFlags.MODAL
                    | Gtk.DialogFlags.DESTROY_WITH_PARENT
                    | Gtk.DialogFlags.USE_HEADER_BAR,
                    type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK_CANCEL,
                    message_format="File exists. Overwrite?",
                )
                response = warn_dialog.run()
                warn_dialog.destroy()
                if response != Gtk.ResponseType.OK:
                    return

            save_content = {
                "General": {"Name": examname, "Date": self.examdate},
                "PointTable": self.point_table.as_dict(),
            }
            task_settings = []
            for t in self.tasks:
                task_settings.append(t.as_dict())
            save_content["Tasks"] = task_settings
            grading_entries = []
            for row in self.grading_rows:
                grading_entries.append(row.as_dict())
            save_content["Grading"] = grading_entries

            with filepath.open("w") as savefile:
                savefile.write(json.dumps(save_content, indent=4, sort_keys=True))

            # dialog = Gtk.MessageDialog(
            #     self.window,
            #     Gtk.DialogFlags.MODAL
            #     | Gtk.DialogFlags.DESTROY_WITH_PARENT
            #     | Gtk.DialogFlags.USE_HEADER_BAR,
            #     Gtk.MessageType.INFO,
            #     Gtk.ButtonsType.OK,
            #     "File Saved",
            # )
            # dialog.show_all()
            # dialog.run()
            # dialog.destroy()

    def open(self, widget):
        file_choose_dialog = Gtk.FileChooserDialog(
            "Open File",
            self.window,
            Gtk.FileChooserAction.OPEN,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )
        exam_file_filter = Gtk.FileFilter()
        exam_file_filter.set_name("Exam Grading Files")
        exam_file_filter.add_pattern("*.examgrades")
        file_choose_dialog.add_filter(exam_file_filter)
        all_files_filter = Gtk.FileFilter()
        all_files_filter.set_name("All Files")
        all_files_filter.add_pattern("*")

        response = file_choose_dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = Path(file_choose_dialog.get_filename())
            file_choose_dialog.destroy()
            if not self.clear(None):
                return
            exam = {}
            with filepath.open("r") as f:
                exam = json.loads(f.read())
            try:
                self.examname_entry.set_text(exam["General"]["Name"])
                self.examdate = exam["General"]["Date"]
                self.builder.get_object("examdate_button_label").set_text(self.examdate)

                for t in exam["Tasks"]:
                    self.add_task(t["Name"], t["Max_Points"], t["ID"])

                self.builder.get_object("passing_spin_but").set_value(
                    exam["PointTable"]["passing"]
                )
                self.builder.get_object("stepsize_spin_but").set_value(
                    exam["PointTable"]["step"]
                )
                self.update_grade_table(None, False)

                self.block_histogram_update = True
                for grading in exam["Grading"]:
                    points = []
                    for t in self.tasks:
                        points.append(float(grading["Tasks"][str(t.id)]))
                    points.append(float(grading["Tasks"]["Additional_Points"]))

                    self.grading_rows.append(
                        GradingRow(
                            grading["StudentID"],
                            grading["First_Name"],
                            grading["Surname"],
                            self.tasks,
                            self.grade_calculation,
                            self.update_histogram,
                            points,
                        ),
                    )

                self.grading_rows = list(sorted(self.grading_rows, key=lambda r: r.stud_id))
                for row in self.grading_rows:
                    self.grading_table.add(row)
                self.grading_table.show_all()
                self.block_histogram_update = False
                self.update_histogram(None, False)

            except ValueError:
                print("ERROR: Corrupt file")
                self.clear(None)

            self.modified = False

    def clear(self, widget) -> bool:
        """
        returns True, if the state was cleared
        """
        if self.modified:
            warn_dialog = Gtk.MessageDialog(
                self.window,
                Gtk.DialogFlags.MODAL
                | Gtk.DialogFlags.DESTROY_WITH_PARENT
                | Gtk.DialogFlags.USE_HEADER_BAR,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format="This will erase all unsaved modifications",
            )
            response = warn_dialog.run()
            warn_dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return False

        self.examname_entry.set_text("")
        # TODO Date
        self.clear_tasks()
        self.clear_grading_rows()

        self.builder.get_object("passing_spin_but").set_value(10.0)
        self.builder.get_object("stepsize_spin_but").set_value(1.0)
        self.update_grade_table(None)
        self.update_histogram(None, False)
        self.modified = False

        return True


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
        grade_calculation: Callable[[MainWindow, Tuple[float, bool]], str],
        update_callback: Callable[[MainWindow], None],
        points: Optional[List[float]] = None,
    ):
        super(Gtk.Box, self).__init__()

        self.stud_id = student_id
        self.student_id_label.set_text(student_id)
        self.first_name_label.set_text(first_name)
        self.surname_label.set_text(surname)
        self.grade_calculation = grade_calculation
        self.update_callback = update_callback

        self.point_entries = {}

        self.additional_points_entry.connect("changed", self.on_update)
        if points is not None:
            self.additional_points_entry.set_text(str(points[-1]))

        self.points = 0.0
        self.points_final = 0.0
        self.grade = ""
        self.grade_final = ""

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
        self.points = sum
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
        self.points_final = sum
        self.total_points_final_label.set_text(str(self.points_final))
        self.grade_final, passed = self.grade_calculation(sum)
        if not passed:
            self.grade_final_label.get_style_context().add_class("error")
        else:
            self.grade_final_label.get_style_context().remove_class("error")
        self.grade_final_label.set_text(str(self.grade_final))
        self.update_callback(self)

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "StudentID": self.student_id_label.get_text(),
            "First_Name": self.first_name_label.get_text(),
            "Surname": self.surname_label.get_text(),
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
