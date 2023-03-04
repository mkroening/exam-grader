import csv
import json
import random
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable, Dict, List, Optional, Tuple

from gi.repository import Gdk, GLib, Gtk
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.figure import Figure

from .csv_import import CsvImportDialog
from .exam import ExamTask, GradeState, GradeType, PointTable
from .grading_table import GradingRow
from .gui_helpers import (
    get_content,
    show_about_dialog,
    successful_with_open_folder_dialog,
)


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
            .warning {
                color: @warning_color;
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
            "on_gradetable_value_changed": self.on_gradetable_changed,
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
        self.point_histogram_area = self.builder.get_object("point_histogram_area")
        self.total_exam_stat = self.builder.get_object("statistics")
        self.task_diagram_box = self.builder.get_object("task_diagram_box")
        self.processing_revealer = self.builder.get_object("processing_revealer")

        self.modified = False
        self.block_histogram_update = False
        self.max_points = 100
        self.point_table = PointTable(10, 5, self.max_points)

        mplfigure = Figure(figsize=(10, 2), dpi=100)
        self.histogramax = mplfigure.add_subplot(111)
        self.histogrambars = self.histogramax.bar(
            self.point_table.labels,
            [3.0] * len(self.point_table.labels),
            width=0.5,
            color=["tab:red"] + ["tab:blue"] * (len(self.point_table.labels) - 1),
        )
        self.histogramax.plot()
        self.canvas = FigureCanvas(mplfigure)
        self.canvas.set_size_request(400, 200)
        self.histogram_area.add_with_viewport(self.canvas)
        self.histogram_area.show_all()

        mplfigure_pts = Figure(figsize=(10, 2), dpi=100)
        self.ptshistogramax = mplfigure_pts.add_subplot(111)
        self.pthistogrambars = self.ptshistogramax.bar(
            range(self.max_points),
            [1.0] * self.max_points,
            width=0.4,
        )
        self.ptshistogramax.plot()
        self.ptscanvas = FigureCanvas(mplfigure_pts)
        self.ptscanvas.set_size_request(400, 200)
        self.point_histogram_area.add_with_viewport(self.ptscanvas)
        self.point_histogram_area.show_all()

        figure_boxplt = Figure(figsize=(10, 2), dpi=100)
        self.boxplt_ax = figure_boxplt.add_subplot(111)
        self.boxplt = self.boxplt_ax.boxplot(
            [[1, 2, 3], [3, 3, 5], [10, 1, 0]], labels=["T1", "T2", "T3"]
        )
        self.boxplt_ax.plot()
        self.boxcanvas = FigureCanvas(figure_boxplt)
        self.boxcanvas.set_size_request(500, 300)
        self.total_exam_stat.add(self.boxcanvas)

        mplfigure_pts = Figure(figsize=(10, 2), dpi=100)
        self.ptshistogramax2 = mplfigure_pts.add_subplot(111)
        self.ptshistogramax2_box = self.ptshistogramax2.twinx()
        self.ptshistogramax2_box.set_ylim(0, 1)
        self.pthistogrambars2 = self.ptshistogramax2.bar(
            range(self.max_points),
            [1.0] * self.max_points,
            width=0.4,
        )

        self.ptshistogramax2.set_title("Exam Point Distributions")
        self.ptshistogramax2.set_ylabel("Count")
        self.ptshistogramax2.set_xlabel("Points")

        self.ptshistogramax2.plot()
        self.ptscanvas2 = FigureCanvas(mplfigure_pts)
        self.ptscanvas2.set_size_request(500, 300)
        self.total_exam_stat.add(self.ptscanvas2)
        self.total_exam_stat.show_all()

        self.taskplots = {}

        self.grading_rows = []
        self.update_histogram(None, False)

        self.tasks: List[ExamTask] = []
        self.add_task("Exampletask", 10, suppress_generations=True)
        self.generate_task_plots()

        self.clear_grading_rows(True)
        self.grading_table.show_all()
        self.rebuild_gradingtable_header()

        self.update_grade_table(None, False)
        self.modified = False

        self.window.show_all()
        self.processing_revealer.set_reveal_child(False)

    def generate_task_plot(self, tasknr: int) -> Dict[str, Any]:
        task = self.tasks[tasknr]
        fig = Figure(figsize=(10, 2), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(f"T{tasknr} - {task.name}")
        ax.set_xlabel("Points")
        ax.set_ylabel("Students")
        nr_point_bars = int(task.max_points * 1 / 0.5 + 1)
        bar = ax.bar(
            [i * 0.5 for i in range(nr_point_bars)],
            [1.0] * nr_point_bars,
            width=0.4,
        )
        ax.plot()
        canvas = FigureCanvas(fig)
        canvas.set_size_request(600, 300)
        d = {}
        d["bar"] = bar
        d["ax"] = ax
        d["canvas"] = canvas
        return d

    def generate_task_plots(self):
        self.boxplt_ax.clear()
        self.taskplots.clear()
        for child in self.task_diagram_box.get_children():
            self.task_diagram_box.remove(child)

        tasknames = []
        for i, t in enumerate(self.tasks):
            self.taskplots[i] = self.generate_task_plot(i)
            self.task_diagram_box.add(self.taskplots[i]["canvas"])
            self.task_diagram_box.show_all()
            tasknames.append(t.name)

    def update_task_plots(self):
        rev_is_active = self.processing_revealer.get_child_revealed()
        self.processing_revealer.set_reveal_child(True)
        tasknames = []
        taskpts = []
        for tn, p in self.taskplots.items():
            th, tp = self.task_histogram(tn)
            taskpts.append(tp)
            for i, b in enumerate(p["bar"]):
                b.set_height(th[float(i) / 2.0])
            p["ax"].relim()
            p["ax"].autoscale_view()
            p["canvas"].draw()
            p["canvas"].flush_events()

        for i, t in enumerate(self.tasks):
            tasknames.append(t.name)

        self.boxplt_ax.clear()
        if len(taskpts) > 0:
            self.boxplt = self.boxplt_ax.boxplot(taskpts, labels=tasknames)
            for i, t in enumerate(self.tasks):
                self.boxplt_ax.hlines(
                    t.max_points, i + 0.7, i + 1.3, linewidth=2, color="black"
                )
            self.boxplt_ax.set_title("Task Point Distributions")
            self.boxplt_ax.set_ylabel("Points")
            self.boxplt_ax.plot()
        self.boxcanvas.draw()
        self.boxcanvas.flush_events()

        self.update_histogram(None, was_modified=False, redraw=False)
        self.draw_big_histogram()

        if not rev_is_active:
            self.processing_revealer.set_reveal_child(False)

        return False

    def task_histogram(self, tasknr: int) -> Tuple[Dict[int, int], List[float]]:
        hist = {}
        pts = []
        t = self.tasks[tasknr]
        for label in range(int(t.max_points * 1 / 0.5 + 1.0)):
            hist[float(label / 2.0)] = 0
        for row in self.grading_rows:
            try:
                if (
                    row.grade_type == GradeType.NOTE
                    or row.grade_type == GradeType.BESTANDEN
                ):
                    pts.append(row.get_task_points(tasknr))
                    hist[row.get_task_points(tasknr)] += 1
            except KeyError:
                pass
        return hist, pts

    def main_visible_child_changed(self, widget, data):
        if self.main_stack.get_visible_child_name() == "setup_page":
            self.draw_histogram()
        elif self.main_stack.get_visible_child_name() == "graphs_page":
            GLib.timeout_add(500, self.update_task_plots)

    def draw_histogram(self):
        if (
            self.block_histogram_update
            or self.main_stack.get_visible_child_name() != "setup_page"
        ):
            return
        for i, b in enumerate(self.histogrambars):
            b.set_height(self.histogram[self.point_table.labels[i]])
        self.histogramax.relim()
        self.histogramax.autoscale_view()
        self.canvas.draw()
        self.canvas.flush_events()

        for i, b in enumerate(self.pthistogrambars):
            b.set_height(self.point_histogram[float(i / 2)])
        self.ptshistogramax.relim()
        self.ptshistogramax.autoscale_view()
        self.ptscanvas.draw()
        self.ptscanvas.flush_events()

        if len(self.grading_rows) > 0:
            passed_cnt = len(self.grading_rows) - self.histogram["5.0"]
            self.builder.get_object("passed_label").set_text(str(passed_cnt))
            perc_failed = self.histogram["5.0"] / len(self.grading_rows)
            perc_fail_label = self.builder.get_object("perc_fail_label")
            if perc_failed > 0.5:
                perc_fail_label.get_style_context().add_class("error")
            else:
                perc_fail_label.get_style_context().remove_class("error")
            perc_fail_label.set_text(f"{perc_failed * 100.0:.2f}%")

            points = []
            grades = []
            for r in self.grading_rows:
                try:
                    points.append(float(r.points_final))
                except ValueError:
                    pass
                try:
                    grades.append(float(r.grade_final))
                except ValueError:
                    pass

            self.builder.get_object("avg_grade_label").set_text(
                "{:.2f}".format(mean(grades))
            )
            self.builder.get_object("grade_median_label").set_text(
                "{:.2f}".format(median(grades))
            )
            self.builder.get_object("points_median_label").set_text(
                "{:.2f}".format(median(points))
            )
            self.builder.get_object("points_max_label").set_text(
                "{:.2f}".format(max(points))
            )
            self.builder.get_object("best_grade_label").set_text(str(min(grades)))

            grades_passed = list(
                filter(lambda g: g <= 4.0, grades),
            )
            if len(grades_passed) > 0:
                self.builder.get_object("avg_grade_passed_label").set_text(
                    "{:.2f}".format(mean(grades_passed))
                )
            else:
                self.builder.get_object("avg_grade_passed_label").set_text("0")
        else:
            self.builder.get_object("passed_label").set_text("0")
            self.builder.get_object("perc_fail_label").set_text("0")
            self.builder.get_object("perc_fail_label").get_style_context().remove_class(
                "error"
            )
            self.builder.get_object("avg_grade_label").set_text("0")
            self.builder.get_object("avg_grade_passed_label").set_text("0")
            self.builder.get_object("grade_median_label").set_text("0")
            self.builder.get_object("points_median_label").set_text("0")
            self.builder.get_object("points_max_label").set_text("0")
            self.builder.get_object("best_grade_label").set_text("0")

    def draw_big_histogram(self):
        points = list(
            chain.from_iterable([[p] * cnt for p, cnt in self.point_histogram.items()])
        )
        self.ptshistogramax2_box.clear()
        style = dict(alpha=0.25)
        self.ptshistogramax2_box.boxplot(
            points,
            vert=False,
            positions=[0.5],
            widths=0.1,
            boxprops=style,
            flierprops=style,
            whiskerprops=style,
            capprops=style,
            meanprops=style,
        )
        self.ptshistogramax2_box.set_yticks([])

        for i, b in enumerate(self.pthistogrambars2):
            # b.set_height(self.point_histogram.get(float(i/2), 0.0))
            b.set_height(self.point_histogram[float(i / 2)])

        self.ptshistogramax2.relim()
        self.ptshistogramax2.autoscale_view()
        self.ptscanvas2.draw()
        self.ptscanvas2.flush_events()

    def on_gradetable_changed(self, widget):
        GLib.idle_add(self.update_grade_table, None)

    def update_grade_table(self, widget, was_modified: bool = True):
        if was_modified:
            self.modified = True
        passing_spin = self.builder.get_object("passing_spin_but")
        passing_pts = passing_spin.get_value()
        stepsize_spin_but = self.builder.get_object("stepsize_spin_but")
        stepsize = stepsize_spin_but.get_value()
        self.point_table = PointTable(passing_pts, stepsize, self.max_points, 0.5)
        self.ptshistogramax.clear()
        self.ptshistogramax2.clear()
        self.ptshistogramax2.set_title("Exam Point Distributions")
        self.ptshistogramax2.set_ylabel("Count")
        self.ptshistogramax2.set_xlabel("Points")
        nr_point_bars = int(self.max_points * 1 / 0.5 + 1)
        nr_fail_bars = int(self.point_table.points_max[0] * 2)
        self.pthistogrambars = self.ptshistogramax.bar(
            [i * 0.5 for i in range(nr_point_bars)],
            [1.0] * nr_point_bars,
            width=0.4,
            color=["tab:red"] * nr_fail_bars
            + ["tab:blue"] * (nr_point_bars - nr_fail_bars),
        )
        self.pthistogrambars2 = self.ptshistogramax2.bar(
            [i * 0.5 for i in range(nr_point_bars)],
            [1.0] * nr_point_bars,
            width=0.4,
            color=["tab:red"] * nr_fail_bars
            + ["tab:blue"] * (nr_point_bars - nr_fail_bars),
        )

        for i, grade in enumerate(self.point_table.labels):
            label_from = self.builder.get_object(f"{grade}_from")
            label_from.set_text(f"{self.point_table.points_min[i]}")
            label_to = self.builder.get_object(f"{grade}_to")
            label_to.set_text(f"{self.point_table.points_max[i]}")

        tmp = self.block_histogram_update
        self.block_histogram_update = True
        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.block_histogram_update = tmp
        self.update_histogram(None)
        return False

    def update_histogram(self, widget, was_modified: bool = True, redraw: bool = True):
        if was_modified:
            self.modified = True
        self.histogram = self.generate_histogram()
        self.point_histogram = self.generate_point_histogram()
        for grade in self.point_table.labels:
            label_count = self.builder.get_object(f"{grade}_count")
            label_count.set_text(f"{self.histogram[grade]}")
        self.builder.get_object("point_table").show_all()
        if redraw:
            self.draw_histogram()

    def generate_histogram(self) -> Dict[str, int]:
        hist = {}
        for label in self.point_table.all_labels:
            hist[label] = 0
        for row in self.grading_rows:
            try:
                hist[row.grade_final] += 1
            except KeyError:
                pass
        return hist

    def generate_point_histogram(self) -> Dict[float, int]:
        hist = {}
        for label in range(int(self.point_table.points_maximum * 1 / 0.5 + 1.0)):
            hist[float(label / 2.0)] = 0
        for row in self.grading_rows:
            try:
                if (
                    row.grade_type == GradeType.NOTE
                    or row.grade_type == GradeType.BESTANDEN
                ):
                    hist[row.points_final] += 1
            except KeyError:
                pass
        return hist

    def grade_calculation(
        self, points: float, type: GradeType
    ) -> Tuple[str, GradeState]:
        return self.point_table.grade(points, type)

    def on_about_clicked(self, _widget):
        self.help_menu_popover.popdown()
        show_about_dialog(self.window)

    def on_examname_changed(self, widget):
        self.modified = True

    def on_examdate_clicked(self, widget):
        self.modified = True
        date = widget.get_date()
        self.examdate = f"{date.year}-{date.month+1}-{date.day}"
        self.builder.get_object("examdate_button_label").set_text(self.examdate)
        self.builder.get_object("examdate_button").get_popover().popdown()

    def export(self, _widget):
        file_choose_dialog = Gtk.FileChooserDialog(
            "Export CSV",
            self.window,
            Gtk.FileChooserAction.SAVE,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )
        csv_file_filter = Gtk.FileFilter()
        csv_file_filter.set_name("CSV")
        csv_file_filter.add_mime_type("text/csv")
        file_choose_dialog.add_filter(csv_file_filter)
        all_files_filter = Gtk.FileFilter()
        all_files_filter.set_name("All Files")
        all_files_filter.add_pattern("*")
        examname = self.examname_entry.get_text()
        file_choose_dialog.set_current_name(f"{examname}_results.csv")

        ok_butt = file_choose_dialog.get_widget_for_response(
            Gtk.ResponseType.OK
        )
        ok_butt.set_label("Export")
        ok_butt.get_style_context().add_class("suggested-action")

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
                warn_dialog.get_widget_for_response(
                    response_id=Gtk.ResponseType.OK
                ).get_style_context().add_class("destructive-action")
                response = warn_dialog.run()
                warn_dialog.destroy()
                if response != Gtk.ResponseType.OK:
                    return

            with filepath.open("w", newline="") as f:
                # TODO: Options:
                # - Delimiter
                # - float comma or dot
                # - trailing separator
                writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
                header = ["STUDENT_ID", "FIRST_NAME", "FAMILY_NAME", "ATTEMPTS"]
                for t in self.tasks:
                    header += [t.name.upper()]
                header += [
                    "ADDITIONAL_POINTS",
                    "TOTAL_POINTS",
                    "TOTAL_POINTS_FINAL",
                    "GRADE",
                    "GRADE_FINAL",
                ]
                writer.writerow(header)

                try:
                    for row in self.grading_rows:
                        row.on_update(None)
                        r = [row.stud_id, row.first_name, row.surname, row.trials]
                        for i, t in enumerate(self.tasks):
                            r += [row.get_task_points(i)]
                        r += [row.get_additional_points()]
                        r += [row.points, row.points_final, row.grade, row.grade_final]
                        writer.writerow(r)
                except KeyError:
                    dialog = Gtk.MessageDialog(
                        self.window,
                        Gtk.DialogFlags.MODAL
                        | Gtk.DialogFlags.DESTROY_WITH_PARENT
                        | Gtk.DialogFlags.USE_HEADER_BAR,
                        Gtk.MessageType.ERROR,
                        Gtk.ButtonsType.OK,
                        "CSV generation failed",
                    )
                    dialog.show_all()
                    dialog.run()
                    dialog.destroy()
                else:
                    successful_with_open_folder_dialog(
                        self.window, "Export successful", filepath.parent
                    )

        file_choose_dialog.destroy()

    def add_task(
        self,
        name: str,
        points: int,
        id: Optional[int] = None,
        suppress_generations: bool = False,
    ):
        self.modified = True
        if id is None:
            id = random.randint(1, 1000000000000)
        self.tasks.append(ExamTask(name, points, id))
        self.task_list.remove(self.task_list.get_children()[-1])
        self.task_list.add(TaskRow(id, name, points, self.remove_task))
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        self.max_points = sum(map(lambda t: t.max_points, self.tasks))

        tmp = self.block_histogram_update
        self.block_histogram_update = True
        for row in self.grading_rows:
            row.update_entries(self.tasks)
        self.block_histogram_update = tmp
        if not suppress_generations:
            self.update_grade_table(None)
            self.grading_table.show_all()
            self.rebuild_gradingtable_header()
            self.generate_task_plots()

    def remove_task(self, id: int):
        tasklist_pos = None
        for i, t in enumerate(self.tasks):
            if t.id == id:
                tasklist_pos = i
                self.tasks.remove(t)
                break
        assert tasklist_pos is not None
        # First two items are header and seperator
        self.task_list.remove(self.task_list.get_children()[tasklist_pos + 2])
        self.task_list.show_all()

        self.max_points = sum(map(lambda t: t.max_points, self.tasks))
        self.update_grade_table(None)

        for row in self.grading_rows:
            row.update_entries(self.tasks)
        # self.grading_table.show_all()
        self.rebuild_gradingtable_header()
        self.generate_task_plots()

    def rebuild_gradingtable_header(self):
        for child in self.task_label_box.get_children():
            self.task_label_box.remove(child)
        for i, t in enumerate(self.tasks):
            label = Gtk.Label(f"T{i}:\n{t.name[0:12]}")
            label.set_size_request(90, -1)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_tooltip_text(f"T{i}:\n{t.name}")
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
                warn_dialog.get_widget_for_response(
                    response_id=Gtk.ResponseType.OK
                ).get_style_context().add_class("destructive-action")
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
                trials_col = reader.fieldnames[dialog.trial_nr_combo.get_active()]
                try:
                    for row in reader:
                        stud_id = row[stud_id_col]
                        first_name = row[first_name_col]
                        surname = row[surname_col]
                        trials = row[trials_col]

                        self.grading_rows.append(
                            GradingRow(
                                stud_id,
                                first_name,
                                surname,
                                int(trials),
                                self.tasks,
                                self.grade_calculation,
                                self.update_histogram,
                                self.point_table.liststore,
                            )
                        )
                except ValueError:
                    error_dialog = Gtk.MessageDialog(
                        self.window,
                        Gtk.DialogFlags.MODAL
                        | Gtk.DialogFlags.DESTROY_WITH_PARENT
                        | Gtk.DialogFlags.USE_HEADER_BAR,
                        Gtk.MessageType.ERROR,
                        Gtk.ButtonsType.OK,
                        "Invalid Input",
                    )
                    error_dialog.show_all()
                    error_dialog.run()
                    error_dialog.destroy()

            self.grading_rows = list(sorted(self.grading_rows, key=lambda r: r.stud_id))
            for row in self.grading_rows:
                self.grading_table.add(row)
            self.modified = True

        dialog.destroy()

    def clear_grading_rows(self, add_csv_button: bool = False):
        self.grading_rows.clear()
        for child in self.grading_table.get_children()[2:]:
            self.grading_table.remove(child)
        if add_csv_button:
            csv_import_button = Gtk.Button()
            csv_import_button.set_label("Import from CSV")
            csv_import_button.connect("clicked", self.csv_import)
            csv_import_button.set_size_request(150, -1)
            csv_import_button.set_halign(Gtk.Align.CENTER)
            csv_import_button.get_style_context().add_class("suggested-action")
            self.grading_table.add(csv_import_button)
            self.grading_table.show_all()

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

        ok_butt = file_choose_dialog.get_widget_for_response(
            Gtk.ResponseType.OK
        )
        ok_butt.set_label("Save")
        ok_butt.get_style_context().add_class("suggested-action")

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
                warn_dialog.get_widget_for_response(
                    response_id=Gtk.ResponseType.OK
                ).get_style_context().add_class("destructive-action")
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
        else:
            file_choose_dialog.destroy()

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

        ok_butt = file_choose_dialog.get_widget_for_response(
            Gtk.ResponseType.OK
        )
        ok_butt.set_label("Open")
        ok_butt.get_style_context().add_class("suggested-action")

        response = file_choose_dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = Path(file_choose_dialog.get_filename())
            file_choose_dialog.destroy()
            if not self.clear(None):
                return
            self.grading_table.remove(self.grading_table.get_children()[-1])
            self.processing_revealer.set_reveal_child(True)
            exam = {}
            with filepath.open("r") as f:
                exam = json.loads(f.read())
            try:
                tmp = self.block_histogram_update
                self.block_histogram_update = True
                self.examname_entry.set_text(exam["General"]["Name"])
                self.examdate = exam["General"]["Date"]
                if self.examdate == "":
                    self.builder.get_object("examdate_button_label").set_text(
                        "<Select>"
                    )
                else:
                    self.builder.get_object("examdate_button_label").set_text(
                        self.examdate
                    )

                for t in exam["Tasks"]:
                    self.add_task(
                        t["Name"], t["Max_Points"], t["ID"], suppress_generations=True
                    )

                self.builder.get_object("passing_spin_but").set_value(
                    exam["PointTable"]["passing"]
                )
                self.builder.get_object("stepsize_spin_but").set_value(
                    exam["PointTable"]["step"]
                )
                self.update_grade_table(None, False)
                self.rebuild_gradingtable_header()

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
                            grading["Attempt"],
                            self.tasks,
                            self.grade_calculation,
                            self.update_histogram,
                            GradeType.from_shortname(grading.get("GradeState", "")),
                            points,
                            self.point_table.liststore,
                        ),
                    )

                self.grading_rows = list(
                    sorted(self.grading_rows, key=lambda r: r.stud_id)
                )
                for row in self.grading_rows:
                    self.grading_table.add(row)
                self.grading_table.show_all()
                self.block_histogram_update = tmp
                self.update_histogram(None, False)
                self.generate_task_plots()
                self.update_task_plots()

            except (ValueError, TypeError):
                error_dialog = Gtk.MessageDialog(
                    self.window,
                    Gtk.DialogFlags.MODAL
                    | Gtk.DialogFlags.DESTROY_WITH_PARENT
                    | Gtk.DialogFlags.USE_HEADER_BAR,
                    Gtk.MessageType.ERROR,
                    Gtk.ButtonsType.OK,
                    "Corrupt file - aborting",
                )
                error_dialog.show_all()
                error_dialog.run()
                error_dialog.destroy()
                self.clear(None, force=True)

            self.modified = False
            self.processing_revealer.set_reveal_child(False)
        else:
            file_choose_dialog.destroy()

    def clear(self, widget, force: bool = False) -> bool:
        """
        returns True, if the state was cleared
        """
        if self.modified and not force:
            warn_dialog = Gtk.MessageDialog(
                self.window,
                Gtk.DialogFlags.MODAL
                | Gtk.DialogFlags.DESTROY_WITH_PARENT
                | Gtk.DialogFlags.USE_HEADER_BAR,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format="This will erase all unsaved modifications",
            )
            warn_dialog.get_widget_for_response(
                response_id=Gtk.ResponseType.OK
            ).get_style_context().add_class("destructive-action")
            response = warn_dialog.run()
            warn_dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return False

        self.examname_entry.set_text("")
        self.examdate = ""
        self.builder.get_object("examdate_button_label").set_text("<Select>")
        self.clear_tasks()
        self.clear_grading_rows(True)

        self.builder.get_object("passing_spin_but").set_value(10.0)
        self.builder.get_object("stepsize_spin_but").set_value(1.0)
        self.update_grade_table(None)
        self.ptshistogramax.clear()
        self.update_histogram(None, False)
        self.generate_task_plots()
        self.update_task_plots()
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
        self.points_entry.connect("activate", self.add_clicked)
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
