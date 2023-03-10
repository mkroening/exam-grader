import csv
import json
import random
from itertools import chain
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable, Dict, List, Optional, Tuple

from gi.repository import Gdk, GLib, Gtk, Gio
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .csv_import import CsvImportDialog
from .exam import ExamTask, GradeState, GradeType, PointTable
from .grading_table import (
    AddGradingRow,
    GradeTable,
    GradingRow,
    SortKeys,
    Student,
    Taskpoint,
    grading_row_sort_func,
    grading_row_filter_func,
)
from .gui_helpers import (
    get_content,
    show_about_dialog,
    successful_with_open_folder_dialog,
)
from .histograms import BigPointHistogram, GradeHistogram, PointHistogram


class MainWindow:
    def __init__(self):
        self.builder = Gtk.Builder.new_from_resource("/exam-grader/Main_Window.glade")

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
            "on_quit": self.quit_with_confirmation,
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
            "on_sort_key_changed": self.on_sort_key_changed,
            "on_grade_sep_toggle": self.on_grade_sep_toggle,
            "on_grade_table_button_pressed": self.on_grade_table_button_pressed,
            "on_filter_text_changed": self.on_filter_changed,
            "on_filter_text_clear": self.on_filter_clear,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")
        self.examname_entry = self.builder.get_object("examname_entry")
        self.task_list = self.builder.get_object("task_list")
        self.task_list.add(AddTaskRow(self.add_task))
        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")
        self.new_button = self.builder.get_object("new_button")
        self.save_button = self.builder.get_object("save_button")
        self.csv_import_button = self.builder.get_object("csv_import_button")
        self.grading_table = self.builder.get_object("grading_tabl")
        self.task_label_box = self.builder.get_object("task_label_box")
        self.histogram_area = self.builder.get_object("histogram_area")
        self.point_histogram_area = self.builder.get_object("point_histogram_area")
        self.total_exam_stat = self.builder.get_object("statistics")
        self.task_diagram_box = self.builder.get_object("task_diagram_box")
        self.processing_revealer = self.builder.get_object("processing_revealer")
        self.grade_separators_checkbox = self.builder.get_object(
            "grade_separators_checkbox"
        )
        self.passing_spin = self.builder.get_object("passing_spin_but")
        self.stepsize_spin = self.builder.get_object("stepsize_spin_but")
        self.sort_key_combo = self.builder.get_object("sort_key_combo")
        self.point_table_box = self.builder.get_object("point_table")

        self.accel_group = self.builder.get_object("grading_accel")
        key, mod = Gtk.accelerator_parse("<Control>n")
        self.accel_group.connect(key, mod, 0, self.clear)
        key, mod = Gtk.accelerator_parse("<Control>o")
        self.accel_group.connect(key, mod, 0, self.open)
        key, mod = Gtk.accelerator_parse("<Control>s")
        self.accel_group.connect(key, mod, 0, self.save)
        key, mod = Gtk.accelerator_parse("<Control>i")
        self.accel_group.connect(key, mod, 0, self.csv_import)
        key, mod = Gtk.accelerator_parse("<Control>e")
        self.accel_group.connect(key, mod, 0, self.export)
        key, mod = Gtk.accelerator_parse("<Control>1")
        self.accel_group.connect(key, mod, 0, self.switch_main_stack_setup)
        key, mod = Gtk.accelerator_parse("<Control>2")
        self.accel_group.connect(key, mod, 0, self.switch_main_stack_grading)
        key, mod = Gtk.accelerator_parse("<Control>3")
        self.accel_group.connect(key, mod, 0, self.switch_main_stack_graphs)

        self.stepsize = 1.0
        self.modified = False
        self.block_histogram_update = False
        self.block_grade_table_update = False
        self.max_points = 100
        self.point_table = PointTable(10, 5, self.max_points, min_step=self.stepsize)

        self.tasks: List[ExamTask] = []

        self.sort_key_combo.set_model(SortKeys.as_liststore())
        self.sort_key_combo.set_active(SortKeys.ID)
        self.grading = GradeTable(
            self.tasks, self.point_table, self.grading_table, self.update_histogram
        )
        self.grade_histogram = GradeHistogram(
            self.point_table,
            self.histogram_area,
            viewport=True,
        )
        self.histogram_area.show_all()

        self.point_histogram = PointHistogram(
            self.max_points,
            self.point_histogram_area,
            viewport=True,
            stepsize=self.stepsize,
        )
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

        self.big_histogram = BigPointHistogram(
            self.max_points,
            self.total_exam_stat,
            viewport=False,
            stepsize=self.stepsize,
        )
        self.total_exam_stat.show_all()

        self.taskplots = {}

        self.builder.get_object("grading_table_box").set_center_widget(
            AddGradingRow(self.grading)
        )
        self.add_task("Exampletask", 10, suppress_generations=True)

        self.generate_task_plots()

        self.grading_table.show_all()
        self.rebuild_gradingtable_header()

        self.should_update_histogram = True
        self.update_grade_table(None, False)
        self.modified = False
        self.examdate = ""
        self.lastpath = None

        self.redraw_visible_graphs()
        self.window.show_all()
        self.processing_revealer.set_reveal_child(False)

    def set_buttons_sensitive(self, sens: bool):
        self.new_button.set_sensitive(sens)
        self.open_button.set_sensitive(sens)
        self.save_button.set_sensitive(sens)
        self.csv_import_button.set_sensitive(sens)
        self.export_button.set_sensitive(sens)

    def quit_with_confirmation(self, widget, data):
        if self.modified:
            warn_dialog = Gtk.MessageDialog(
                self.window,
                Gtk.DialogFlags.MODAL
                | Gtk.DialogFlags.DESTROY_WITH_PARENT
                | Gtk.DialogFlags.USE_HEADER_BAR,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format="Unsaved changes, really quit?",
            )
            warn_dialog.get_widget_for_response(
                response_id=Gtk.ResponseType.OK
            ).get_style_context().add_class("destructive-action")
            response = warn_dialog.run()
            warn_dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return True
        # Continue with closing procedure
        Gtk.main_quit(widget)
        return False

    def on_sort_key_changed(self, widget):
        key = SortKeys(widget.get_active())
        self.grading_table.set_sort_func(grading_row_sort_func, key, False)

    def on_filter_changed(self, widget):
        text = widget.get_text()
        if text == "":
            widget.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, False)
        else:
            widget.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, True)
        self.grading_table.set_filter_func(grading_row_filter_func, text, False)

    def on_filter_clear(self, widget, data, event):
        widget.set_text("")
        self.grading_table.set_filter_func(None, None, False)

    def generate_task_plot(self, tasknr: int) -> Dict[str, Any]:
        task = self.tasks[tasknr]
        fig = Figure(figsize=(10, 2), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(f"T{tasknr} - {task.name}")
        ax.set_xlabel("Points")
        ax.set_ylabel("Students")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
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
        canvas.draw()
        canvas.flush_events()
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
            th, tp = self.grading.task_histogram_and_points(self.tasks[tn].id)
            taskpts.append(tp)
            for i, b in enumerate(p["bar"]):
                b.set_height(th[float(i) / 2.0])
            p["ax"].relim()
            p["ax"].autoscale_view()
            p["canvas"].draw()
            p["canvas"].flush_events()

        for i, t in enumerate(self.tasks):
            tasknames.append(("\n" if i % 2 == 1 else "") + t.name)

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

        self.big_histogram.draw()

        if not rev_is_active:
            self.processing_revealer.set_reveal_child(False)

        return False

    def main_visible_child_changed(self, widget, data=None):
        GLib.timeout_add(500, self.redraw_visible_graphs)

    def redraw_visible_graphs(self):
        if self.main_stack.get_visible_child_name() == "setup_page":
            if self.should_update_histogram:
                self.update_histogram()
            self.grade_histogram.draw()
            self.point_histogram.draw()
            self.update_statistics()
        elif self.main_stack.get_visible_child_name() == "graphs_page":
            if self.should_update_histogram:
                self.update_histogram()
            self.big_histogram.draw()
            self.update_task_plots()

    def update_statistics(self, widget=None):
        points, grades = self.grading.point_and_grades_list()
        if len(points) > 0:
            grades_numeric = [float(g) for g in grades if g in self.point_table.labels]
            gplist = list(
                filter(
                    lambda gp: self.point_table.has_passed(gp[0]), zip(grades, points)
                )
            )
            grades_passed = list(
                map(lambda gp: float(gp[0]), gplist),
            )
            points_passed = list(
                map(lambda gp: gp[1], gplist),
            )

            passed_cnt = len(grades_passed)
            self.builder.get_object("passed_label").set_text(str(passed_cnt))
            perc_failed = 1 - passed_cnt / len(grades)
            perc_fail_label = self.builder.get_object("perc_fail_label")
            if perc_failed > 0.5:
                perc_fail_label.get_style_context().add_class("error")
            else:
                perc_fail_label.get_style_context().remove_class("error")
            perc_fail_label.set_text(f"{perc_failed * 100.0:.2f}%")

            self.builder.get_object("participants_label").set_text(str(len(grades)))
            self.builder.get_object("avg_grade_label").set_text(
                "{:.2f}".format(mean(grades_numeric))
            )
            self.builder.get_object("grade_median_label").set_text(
                "{:.2f}".format(median(grades_numeric))
            )
            self.builder.get_object("points_median_label").set_text(
                "{:.2f}".format(median(points))
            )
            self.builder.get_object("points_average_label").set_text(
                "{:.1f}".format(mean(points))
            )
            self.builder.get_object("points_max_label").set_text(
                "{:.2f}".format(max(points))
            )
            self.builder.get_object("best_grade_label").set_text(str(min(grades)))

            if len(points_passed) > 0:
                self.builder.get_object("points_average_passed_label").set_text(
                    "{:.1f}".format(mean(points_passed))
                )
            else:
                self.builder.get_object("points_average_passed_label").set_text("0")
            if len(grades_passed) > 0:
                self.builder.get_object("avg_grade_passed_label").set_text(
                    "{:.2f}".format(mean(grades_passed))
                )
            else:
                self.builder.get_object("avg_grade_passed_label").set_text("0")
        else:
            self.builder.get_object("participants_label").set_text("0")
            self.builder.get_object("passed_label").set_text("0")
            self.builder.get_object("perc_fail_label").set_text("0")
            self.builder.get_object("perc_fail_label").get_style_context().remove_class(
                "error"
            )
            self.builder.get_object("avg_grade_label").set_text("0")
            self.builder.get_object("avg_grade_passed_label").set_text("0")
            self.builder.get_object("points_average_label").set_text("0")
            self.builder.get_object("points_average_passed_label").set_text("0")
            self.builder.get_object("grade_median_label").set_text("0")
            self.builder.get_object("points_median_label").set_text("0")
            self.builder.get_object("points_max_label").set_text("0")
            self.builder.get_object("best_grade_label").set_text("0")

    def on_gradetable_changed(self, widget):
        self.update_grade_table()

        GLib.timeout_add(200, self.redraw_visible_graphs)

    def update_max_points(self):
        # If only the maxpoints change, we don't need to update the grading and grade histogram
        passing_pts = self.passing_spin.get_value()
        stepsize = self.stepsize_spin.get_value()
        self.point_table = PointTable(
            passing_pts, stepsize, self.max_points, min_step=self.stepsize
        )
        new_max = self.point_table.points_max[-1]
        label_to = self.builder.get_object("1.0_to")
        label_to.set_text(f"{new_max}")
        self.point_histogram.relimit_x_axis(new_max)
        self.big_histogram.relimit_x_axis(new_max)

    def on_grade_sep_toggle(self, widget):
        if self.grade_separators_checkbox.get_active():
            self.point_histogram.update_separators(self.point_table.points_min)
            self.big_histogram.update_separators(self.point_table.points_min)
        else:
            self.point_histogram.clear_separators()
            self.big_histogram.clear_separators()
        if self.main_stack.get_visible_child_name() == "setup_page":
            self.point_histogram.draw()
        elif self.main_stack.get_visible_child_name() == "graphs_page":
            self.big_histogram.draw()

    def update_grade_table(
        self,
        widget=None,
        was_modified: bool = True,
    ):
        if self.block_grade_table_update:
            return
        if was_modified:
            self.modified = True
        passing_pts = self.passing_spin.get_value()
        stepsize = self.stepsize_spin.get_value()
        self.point_table = PointTable(
            passing_pts, stepsize, self.max_points, min_step=self.stepsize
        )

        tmp = self.block_histogram_update
        self.block_histogram_update = True
        self.grading.update_point_table(self.point_table)
        self.block_histogram_update = tmp
        self.update_histogram(None)

        for i, grade in enumerate(self.point_table.labels):
            label_from = self.builder.get_object(f"{grade}_from")
            label_from.set_text(f"{self.point_table.points_min[i]}")
            label_to = self.builder.get_object(f"{grade}_to")
            label_to.set_text(f"{self.point_table.points_max[i]}")

        self.point_histogram.recolor(self.point_table.points_max[0])
        if self.grade_separators_checkbox.get_active():
            self.point_histogram.update_separators(self.point_table.points_min)
            self.big_histogram.update_separators(self.point_table.points_min)
        else:
            self.point_histogram.clear_separators()
            self.big_histogram.clear_separators()
        self.big_histogram.recolor(self.point_table.points_max[0])
        self.grade_histogram.update_heights_from_histogram(self.g_histogram)
        return False

    # The points and thus the grades have changed
    def update_histogram(self, widget=None, was_modified: bool = True):
        if self.block_histogram_update:
            return
        if was_modified:
            self.modified = True
        if (
            self.main_stack.get_visible_child_name() != "setup_page"
            and self.main_stack.get_visible_child_name() != "graphs_page"
        ):
            self.should_update_histogram = True
            return

        self.g_histogram = self.grading.grade_histogram()
        self.p_histogram = self.grading.point_histogram()

        for grade in self.point_table.labels:
            label_count = self.builder.get_object(f"{grade}_count")
            label_count.set_text(f"{self.g_histogram[grade]}")
        self.builder.get_object("point_table").show_all()

        self.point_histogram.update_heights_from_histogram(self.p_histogram)
        self.big_histogram.update_heights_from_histogram(self.p_histogram)
        self.grade_histogram.update_heights_from_histogram(self.g_histogram)
        self.should_update_histogram = False

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

    def export(self, *args):
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
        if self.lastpath is not None:
            file_choose_dialog.set_current_folder(self.lastpath)
        examname = self.examname_entry.get_text()
        file_choose_dialog.set_current_name(f"{examname}_results.csv")

        ok_butt = file_choose_dialog.get_widget_for_response(Gtk.ResponseType.OK)
        ok_butt.set_label("Export")
        ok_butt.get_style_context().add_class("suggested-action")

        response = file_choose_dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = Path(file_choose_dialog.get_filename())
            self.lastpath = str(filepath.parent)
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
                self.set_buttons_sensitive(False)
                # TODO: Options:
                # - Delimiter
                # - float comma or dot
                # - trailing separator
                writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)

                try:
                    tab = self.grading.as_table()
                    for line in tab:
                        writer.writerow(line)
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
                self.set_buttons_sensitive(True)

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
        new_task = ExamTask(name, points, id)
        self.tasks.append(new_task)
        self.task_list.remove(self.task_list.get_children()[-1])
        self.task_list.add(TaskRow(id, name, points, self.remove_task))
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        self.max_points = sum(map(lambda t: t.max_points, self.tasks))

        tmp = self.block_histogram_update
        self.block_histogram_update = True
        self.grading.update_after_add_task(new_task)
        self.block_histogram_update = tmp
        self.update_max_points()

        if not suppress_generations:
            self.rebuild_gradingtable_header()
            self.generate_task_plots()
            self.redraw_visible_graphs()

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
        self.point_histogram.relimit_x_axis(self.max_points)
        self.big_histogram.relimit_x_axis(self.max_points)
        self.update_grade_table(None)

        self.grading.update_after_remove_task(id)
        self.update_histogram()
        self.redraw_visible_graphs()
        self.rebuild_gradingtable_header()

        self.generate_task_plots()

    def rebuild_gradingtable_header(self):
        for child in self.task_label_box.get_children():
            self.task_label_box.remove(child)
        for i, t in enumerate(self.tasks):
            label = Gtk.Label(f"T{i+1}:\n{t.name[0:12]}")
            label.set_size_request(90, -1)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_tooltip_text(f"Task {i+1}:\n{t.name}")
            self.task_label_box.add(label)
        self.task_label_box.show_all()

    def csv_import(self, *args):
        dialog = CsvImportDialog(self.window, self.lastpath)
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

            self.grading.clear_rows()

            self.lastpath = str(dialog.csv.parent)
            with dialog.csv.open(newline="") as csv_f:
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=dialog.csv_dialect)
                stud_id_col = reader.fieldnames[dialog.stud_id_combo.get_active()]
                first_name_col = reader.fieldnames[dialog.first_name_combo.get_active()]
                surname_col = reader.fieldnames[dialog.surname_combo.get_active()]
                attempts_col = reader.fieldnames[dialog.trial_nr_combo.get_active()]
                try:
                    zero_points = [Taskpoint(task.id, 0.0) for task in self.tasks]
                    for row in reader:
                        stud = Student(
                            id=row[stud_id_col],
                            first_name=row[first_name_col],
                            surname=row[surname_col],
                            attempts=int(row[attempts_col]),
                            points=zero_points,
                        )

                        self.grading.add_student(stud)

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

            self.modified = True

        dialog.destroy()

    def clear_tasks(self, rebuild_gradingtable: bool = False, *args):
        # First two items are header and seperator
        for t in self.task_list.get_children()[2:]:
            self.task_list.remove(t)
        self.tasks.clear()
        self.task_list.add(AddTaskRow(self.add_task))
        self.task_list.show_all()

        self.grading.update_after_clear_tasks()

        self.rebuild_gradingtable_header()

    def save(self, widget, *args):
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
        if self.lastpath is not None:
            file_choose_dialog.set_current_folder(self.lastpath)
        file_choose_dialog.set_current_name(f"{examname}.examgrades")

        ok_butt = file_choose_dialog.get_widget_for_response(Gtk.ResponseType.OK)
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
            self.lastpath = str(filepath.parent)

            save_content = {
                "General": {"Name": examname, "Date": self.examdate},
                "PointTable": self.point_table.as_dict(),
            }
            task_settings = []
            for t in self.tasks:
                task_settings.append(t.as_dict())
            save_content["Tasks"] = task_settings
            save_content["Grading"] = self.grading.export()

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

    def open(self, widget, *args):
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
        if self.lastpath is not None:
            file_choose_dialog.set_current_folder(self.lastpath)

        ok_butt = file_choose_dialog.get_widget_for_response(Gtk.ResponseType.OK)
        ok_butt.set_label("Open")
        ok_butt.get_style_context().add_class("suggested-action")

        response = file_choose_dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = Path(file_choose_dialog.get_filename())
            self.lastpath = str(filepath.parent)
            file_choose_dialog.destroy()
            if not self.clear(None, force=False, regenerate_graphs_and_stat=False):
                return
            self.set_buttons_sensitive(False)
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

                tmp = self.block_grade_table_update
                self.block_grade_table_update = True
                self.passing_spin.set_value(exam["PointTable"]["passing"])
                self.stepsize_spin.set_value(exam["PointTable"]["step"])
                self.block_grade_table_update = tmp

                self.update_max_points()
                self.point_histogram.relimit_x_axis(self.point_table.points_max[-1])
                self.big_histogram.relimit_x_axis(self.point_table.points_max[-1])
                self.update_grade_table(None, False)
                self.rebuild_gradingtable_header()

                for stud in exam["Grading"]:
                    self.grading.add_student(Student.from_dict(stud))

                self.block_histogram_update = tmp
                self.update_histogram(None, False)
                self.generate_task_plots()

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
        self.redraw_visible_graphs()
        self.set_buttons_sensitive(True)

    def clear(
        self, widget, force: bool = False, regenerate_graphs_and_stat: bool = True
    ) -> bool:
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

        self.set_buttons_sensitive(False)
        self.examname_entry.set_text("")
        self.examdate = ""
        self.builder.get_object("examdate_button_label").set_text("<Select>")
        self.grading.clear_rows()
        self.clear_tasks()

        tmp = self.block_grade_table_update
        self.block_grade_table_update = True
        self.passing_spin.set_value(10.0)
        self.stepsize_spin.set_value(1.0)
        self.block_grade_table_update = tmp

        self.max_points = 20.0
        self.point_histogram.clear_separators()
        self.point_histogram.relimit_x_axis(self.max_points)
        self.big_histogram.clear_separators()
        self.big_histogram.relimit_x_axis(self.max_points)
        if regenerate_graphs_and_stat:
            self.generate_task_plots()
            self.update_grade_table(None)
            self.redraw_visible_graphs()
        self.modified = False
        self.set_buttons_sensitive(True)

        return True

    def on_grade_table_button_pressed(self, widget, data):
        if data.get_button() == (True, 3):
            menu = Gtk.Menu()
            entry = Gtk.MenuItem.new_with_label("Copy Table")
            entry.connect("activate", self.copy_grade_table)
            menu.add(entry)
            menu.attach_to_widget(self.point_table_box)
            menu.show_all()
            menu.popup_at_pointer(data)

    def copy_grade_table(self, widget):
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.set_text(self.point_table.as_str(), -1)

    def switch_main_stack_setup(self, *args):
        self.main_stack.set_visible_child_name("setup_page")

    def switch_main_stack_grading(self, *args):
        self.main_stack.set_visible_child_name("grading_page")

    def switch_main_stack_graphs(self, *args):
        self.main_stack.set_visible_child_name("graphs_page")


@Gtk.Template(resource_path="/exam-grader/Add_Task_Row.glade")
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


@Gtk.Template(resource_path="/exam-grader/Task_Row.glade")
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
