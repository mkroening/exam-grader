import csv
import json
import random
from logging import error
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable, Dict, List, Optional

import chardet
from gi.repository import Gdk, Gio, GLib, Gtk
from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .csv_import import CsvImportConfig, CsvImportDialog
from .csv_results_import import CsvResultImportDialog, CsvResultImportConfig
from .csv_patch import CsvPatchDialog
from .exam import ExamTask, PointTable
from .grading_table import (
    AddGradingRow,
    GradeTable,
    SortKeys,
    Student,
    Taskpoint,
    grading_row_filter_func,
    grading_row_sort_func,
)
from .gui_helpers import (
    create_file_dialog,
    get_content,
    show_about_dialog,
    successful_with_open_folder_dialog,
    clear_container,
)
from .histograms import BigPointHistogram, GradeHistogram, PointHistogram
from .savefile import DecryptDialog, EncryptDialog, create_save_content, decrypt_exam


@Gtk.Template(resource_path="/exam-grader/Main_Window.ui")
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "main_window"

    main_stack = Gtk.Template.Child("main_stack")
    help_menu_popover = Gtk.Template.Child("help_menu_popover")
    examname_entry = Gtk.Template.Child("examname_entry")
    task_list = Gtk.Template.Child("task_list")
    export_button = Gtk.Template.Child("export_button")
    open_button = Gtk.Template.Child("open_button")
    new_button = Gtk.Template.Child("new_button")
    save_button = Gtk.Template.Child("save_button")
    csv_import_button = Gtk.Template.Child("csv_import_button")
    grading_table = Gtk.Template.Child("grading_tabl")
    task_label_box = Gtk.Template.Child("task_label_box")
    histogram_area = Gtk.Template.Child("histogram_area")
    point_histogram_area = Gtk.Template.Child("point_histogram_area")
    total_exam_stat = Gtk.Template.Child("statistics")
    task_diagram_box = Gtk.Template.Child("task_diagram_box")
    processing_revealer = Gtk.Template.Child("processing_revealer")
    grade_separators_checkbox = Gtk.Template.Child("grade_separators_checkbox")
    passing_spin = Gtk.Template.Child("passing_spin_but")
    stepsize_spin = Gtk.Template.Child("stepsize_spin_but")
    sort_key_combo = Gtk.Template.Child("sort_key_combo")
    point_table_box = Gtk.Template.Child("point_table")
    grading_table_box = Gtk.Template.Child("grading_table_box")

    passed_label = Gtk.Template.Child("passed_label")
    perc_fail_label = Gtk.Template.Child("perc_fail_label")
    participants_label = Gtk.Template.Child("participants_label")
    avg_grade_label = Gtk.Template.Child("avg_grade_label")
    avg_grade_passed_label = Gtk.Template.Child("avg_grade_passed_label")
    best_grade_label = Gtk.Template.Child("best_grade_label")
    grade_median_label = Gtk.Template.Child("grade_median_label")
    points_median_label = Gtk.Template.Child("points_median_label")
    points_average_label = Gtk.Template.Child("points_average_label")
    points_max_label = Gtk.Template.Child("points_max_label")
    points_average_passed_label = Gtk.Template.Child("points_average_passed_label")

    examdate_button = Gtk.Template.Child("examdate_button")
    label_5_0_from = Gtk.Template.Child("5.0_from")
    label_4_0_from = Gtk.Template.Child("4.0_from")
    label_3_7_from = Gtk.Template.Child("3.7_from")
    label_3_3_from = Gtk.Template.Child("3.3_from")
    label_3_0_from = Gtk.Template.Child("3.0_from")
    label_2_7_from = Gtk.Template.Child("2.7_from")
    label_2_3_from = Gtk.Template.Child("2.3_from")
    label_2_0_from = Gtk.Template.Child("2.0_from")
    label_1_7_from = Gtk.Template.Child("1.7_from")
    label_1_3_from = Gtk.Template.Child("1.3_from")
    label_1_0_from = Gtk.Template.Child("1.0_from")
    label_5_0_to = Gtk.Template.Child("5.0_to")
    label_4_0_to = Gtk.Template.Child("4.0_to")
    label_3_7_to = Gtk.Template.Child("3.7_to")
    label_3_3_to = Gtk.Template.Child("3.3_to")
    label_3_0_to = Gtk.Template.Child("3.0_to")
    label_2_7_to = Gtk.Template.Child("2.7_to")
    label_2_3_to = Gtk.Template.Child("2.3_to")
    label_2_0_to = Gtk.Template.Child("2.0_to")
    label_1_7_to = Gtk.Template.Child("1.7_to")
    label_1_3_to = Gtk.Template.Child("1.3_to")
    label_1_0_to = Gtk.Template.Child("1.0_to")
    label_5_0_count = Gtk.Template.Child("5.0_count")
    label_4_0_count = Gtk.Template.Child("4.0_count")
    label_3_7_count = Gtk.Template.Child("3.7_count")
    label_3_3_count = Gtk.Template.Child("3.3_count")
    label_3_0_count = Gtk.Template.Child("3.0_count")
    label_2_7_count = Gtk.Template.Child("2.7_count")
    label_2_3_count = Gtk.Template.Child("2.3_count")
    label_2_0_count = Gtk.Template.Child("2.0_count")
    label_1_7_count = Gtk.Template.Child("1.7_count")
    label_1_3_count = Gtk.Template.Child("1.3_count")
    label_1_0_count = Gtk.Template.Child("1.0_count")

    def __init__(self, **kargs):
        super(Gtk.ApplicationWindow, self).__init__(**kargs)

        self.task_list.append(AddTaskRow(self.add_task))

        shortcut_cont = Gtk.ShortcutController()
        for trigger, action in [
            ["<Control>n", self.on_clear_clicked],
            ["<Control>o", self.open],
            ["<Control>s", self.on_save_clicked],
            ["<Control>i", self.on_csv_import_clicked],
            ["<Control>e", self.on_csv_export_clicked],
            ["<Control>1", self.switch_main_stack_setup],
            ["<Control>2", self.switch_main_stack_grading],
            ["<Control>3", self.switch_main_stack_results],
            ["<Control>4", self.switch_main_stack_graphs],
        ]:
            shortcut_cont.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(trigger),
                    Gtk.CallbackAction.new(action, None),
                )
            )
        self.add_controller(shortcut_cont)

        # Grade table cotext menu setup
        evk = Gtk.GestureClick.new()
        evk.set_button(3)  # Right click
        evk.connect("pressed", self.on_grade_table_button_pressed)
        self.point_table_box.add_controller(evk)
        action = Gio.SimpleAction.new("copy_grade_table", None)
        action.connect("activate", self.copy_grade_table)
        self.add_action(action)
        menu = Gio.Menu.new()
        menu.append("Copy Table", "win.copy_grade_table")
        self.grade_table_popover = Gtk.PopoverMenu()
        self.grade_table_popover.set_menu_model(menu)
        self.grade_table_popover.set_parent(self.point_table_box)
        # This is somehow necessary to us the offset calculation.
        self.grade_table_popover.set_pointing_to(Gdk.Rectangle(0, 0, 0, 0))
        self.grade_table_popover.set_has_arrow(False)

        self.min_point_step = 0.5
        self.modified = False
        self.block_histogram_update = False
        self.block_grade_table_update = False
        self.max_points = 100
        self.point_table = PointTable(
            10, 5, self.max_points, min_step=self.min_point_step
        )

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

        self.point_histogram = PointHistogram(
            self.max_points,
            self.point_histogram_area,
            viewport=True,
            bucket_size=self.min_point_step,
        )

        figure_boxplt = Figure(figsize=(10, 2), dpi=100)
        self.boxplt_ax = figure_boxplt.add_subplot(111)
        self.boxplt_ax.plot()
        self.boxcanvas = FigureCanvas(figure_boxplt)
        self.boxcanvas.set_size_request(500, 300)
        self.total_exam_stat.append(self.boxcanvas)

        self.big_histogram = BigPointHistogram(
            self.max_points,
            self.total_exam_stat,
            viewport=False,
            bucket_size=self.min_point_step,
        )

        self.taskplots = {}

        self.grading_table_box.set_center_widget(AddGradingRow(self.grading))
        self.add_task("Exampletask", 10, suppress_generations=True)

        self.generate_task_plots()

        self.rebuild_gradingtable_header()

        self.should_update_histogram = True
        self.modified = False
        self.examdate = ""
        self.lastpath = None

        self.passwd = None

        self.redraw_visible_graphs()
        self.processing_revealer.set_reveal_child(False)

        self.g_histogram = self.grading.grade_histogram()
        self.p_histogram = self.grading.point_histogram()

    def recreate_graphs(self):
        clear_container(self.total_exam_stat, 0)
        self.big_histogram = BigPointHistogram(
            self.max_points,
            self.total_exam_stat,
            viewport=False,
            bucket_size=self.min_point_step,
        )
        self.generate_task_plots()
        self.grade_histogram = GradeHistogram(
            self.point_table,
            self.histogram_area,
            viewport=True,
        )
        self.point_histogram = PointHistogram(
            self.max_points,
            self.point_histogram_area,
            viewport=True,
            bucket_size=self.min_point_step,
        )

    def set_buttons_sensitive(self, sens: bool):
        self.new_button.set_sensitive(sens)
        self.open_button.set_sensitive(sens)
        self.save_button.set_sensitive(sens)
        self.csv_import_button.set_sensitive(sens)
        self.export_button.set_sensitive(sens)

    @Gtk.Template.Callback()
    def quit_with_confirmation(self, widget):
        if self.modified:
            warn_dialog = Gtk.AlertDialog()
            warn_dialog.set_message("Warning")
            warn_dialog.set_detail("Unsaved changes, really quit?")
            warn_dialog.set_modal(True)
            warn_dialog.set_buttons(["Cancel", "Ok"])
            warn_dialog.set_cancel_button(0)
            warn_dialog.set_default_button(0)
            # warn_dialog.get_cancel_button().get_style_context().add_class("destructive-action")
            warn_dialog.choose(self, None, self.perform_quit, None)
            return True
        # Continue with closing procedure
        return False

    def perform_quit(self, source_obj, async_res, data):
        result = source_obj.choose_finish(async_res)
        if result == 1:
            self.destroy()

    @Gtk.Template.Callback()
    def on_sort_key_changed(self, widget):
        key = SortKeys(widget.get_active())
        self.grading_table.set_sort_func(grading_row_sort_func, key, False)

    @Gtk.Template.Callback()
    def on_filter_changed(self, widget):
        text = widget.get_text()
        if text == "":
            widget.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, False)
        else:
            widget.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, True)
        self.grading_table.set_filter_func(grading_row_filter_func, text, False)

    @Gtk.Template.Callback()
    def on_filter_clear(self, widget, data):
        widget.set_text("")
        self.grading_table.set_filter_func(None, None, False)

    def generate_task_plot(self, tasknr: int) -> Dict[str, Any]:
        task = self.tasks[tasknr]
        fig = Figure(figsize=(10, 2), dpi=100)
        fig.subplots_adjust(bottom=0.15)
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
        d: Dict[str, Any] = {}
        d["bar"] = bar
        d["ax"] = ax
        d["canvas"] = canvas
        canvas.draw()
        canvas.flush_events()
        return d

    def generate_task_plots(self):
        self.boxplt_ax.clear()
        self.taskplots.clear()

        clear_container(self.task_diagram_box, 0)

        tasknames = []
        for i, t in enumerate(self.tasks):
            self.taskplots[i] = self.generate_task_plot(i)
            self.task_diagram_box.append(self.taskplots[i]["canvas"])
            # self.task_diagram_box.show_all()
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
            self.boxplt_ax.violinplot(taskpts, showmedians=True)
            self.boxplt_ax.set_xticks(
                [y + 1 for y in range(len(taskpts))], labels=tasknames
            )
            maxpoints = 1
            for i, t in enumerate(self.tasks):
                self.boxplt_ax.hlines(
                    t.max_points, i + 0.7, i + 1.3, linewidth=2, color="black"
                )
                if t.max_points > maxpoints:
                    maxpoints = t.max_points
            self.boxplt_ax.set_ylim(ymin=0, ymax=maxpoints)
            self.boxplt_ax.set_title("Task Point Distributions")
            self.boxplt_ax.set_ylabel("Points")
            self.boxplt_ax.plot()
        self.boxcanvas.draw()
        self.boxcanvas.flush_events()

        self.big_histogram.draw()

        if not rev_is_active:
            self.processing_revealer.set_reveal_child(False)

        return False

    @Gtk.Template.Callback()
    def main_visible_child_changed(self, widget, data=None):
        GLib.timeout_add(500, self.redraw_visible_graphs)

    def redraw_visible_graphs(self):
        if self.main_stack.get_visible_child_name() == "grading_page":
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
            self.passed_label.set_text(str(passed_cnt))
            perc_failed = 1 - passed_cnt / len(grades)
            perc_fail_label = self.perc_fail_label
            if perc_failed > 0.5:
                perc_fail_label.get_style_context().add_class("error")
            else:
                perc_fail_label.get_style_context().remove_class("error")
            perc_fail_label.set_text(f"{perc_failed * 100.0:.2f}%")

            self.participants_label.set_text(str(len(grades)))
            self.avg_grade_label.set_text("{:.2f}".format(mean(grades_numeric)))
            self.grade_median_label.set_text("{:.2f}".format(median(grades_numeric)))
            self.points_median_label.set_text("{:.2f}".format(median(points)))
            self.points_average_label.set_text("{:.1f}".format(mean(points)))
            self.points_max_label.set_text("{:.2f}".format(max(points)))
            self.best_grade_label.set_text(str(min(grades)))

            if len(points_passed) > 0:
                self.points_average_passed_label.set_text(
                    "{:.1f}".format(mean(points_passed))
                )
            else:
                self.points_average_passed_label.set_text("0")
            if len(grades_passed) > 0:
                self.avg_grade_passed_label.set_text(
                    "{:.2f}".format(mean(grades_passed))
                )
            else:
                self.avg_grade_passed_label.set_text("0")
        else:
            self.participants_label.set_text("0")
            self.passed_label.set_text("0")
            self.perc_fail_label.set_text("0")
            self.perc_fail_label.get_style_context().remove_class("error")
            self.avg_grade_label.set_text("0")
            self.avg_grade_passed_label.set_text("0")
            self.points_average_label.set_text("0")
            self.points_average_passed_label.set_text("0")
            self.grade_median_label.set_text("0")
            self.points_median_label.set_text("0")
            self.points_max_label.set_text("0")
            self.best_grade_label.set_text("0")

    @Gtk.Template.Callback()
    def on_gradetable_changed(self, widget):
        self.update_grade_table()

        GLib.timeout_add(200, self.redraw_visible_graphs)

    def update_max_points(self):
        # If only the maxpoints change, we don't need to update the grading and grade histogram
        passing_pts = self.passing_spin.get_value()
        point_step = self.stepsize_spin.get_value()
        self.point_table = PointTable(
            passing_pts, point_step, self.max_points, min_step=self.min_point_step
        )
        new_max = self.point_table.points_max[-1]
        self.grading.point_table = self.point_table
        self.label_1_0_to.set_text(f"{new_max}")
        self.point_histogram.relimit_x_axis(new_max)
        self.big_histogram.relimit_x_axis(new_max)

    @Gtk.Template.Callback()
    def on_grade_sep_toggle(self, widget):
        if self.grade_separators_checkbox.get_active():
            self.point_histogram.update_separators(self.point_table.points_min)
            self.big_histogram.update_separators(self.point_table.points_min)
        else:
            self.point_histogram.clear_separators()
            self.big_histogram.clear_separators()
        if self.main_stack.get_visible_child_name() == "grading_page":
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
        point_step = self.stepsize_spin.get_value()
        self.point_table = PointTable(
            passing_pts, point_step, self.max_points, min_step=self.min_point_step
        )

        tmp = self.block_histogram_update
        self.block_histogram_update = True
        self.grading.update_point_table(self.point_table)
        self.block_histogram_update = tmp
        self.update_histogram(None)

        for i, grade in enumerate(self.point_table.labels):
            label_varname = grade.replace(".", "_")
            label_from = vars(self)[f"label_{label_varname}_from"]
            label_from.set_text(f"{self.point_table.points_min[i]}")
            label_1_0_to = vars(self)[f"label_{label_varname}_to"]
            label_1_0_to.set_text(f"{self.point_table.points_max[i]}")

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
            self.main_stack.get_visible_child_name() != "grading_page"
            and self.main_stack.get_visible_child_name() != "graphs_page"
        ):
            self.should_update_histogram = True
            return

        self.g_histogram = self.grading.grade_histogram()
        self.p_histogram = self.grading.point_histogram()

        for grade in self.point_table.labels:
            label_varname = grade.replace(".", "_")
            label_count = vars(self)[f"label_{label_varname}_count"]
            label_count.set_text(f"{self.g_histogram[grade]}")
        # self.builder.get_object("point_table").show_all()

        self.point_histogram.update_heights_from_histogram(self.p_histogram)
        self.big_histogram.update_heights_from_histogram(self.p_histogram)
        self.grade_histogram.update_heights_from_histogram(self.g_histogram)
        self.should_update_histogram = False

    @Gtk.Template.Callback()
    def on_about_clicked(self, _widget):
        self.help_menu_popover.popdown()
        show_about_dialog(self)

    @Gtk.Template.Callback()
    def on_examname_changed(self, widget):
        self.modified = True

    @Gtk.Template.Callback()
    def on_examdate_clicked(self, widget):
        self.modified = True
        date = widget.get_date()
        self.examdate = (
            f"{date.get_year()}-{date.get_month()}-{date.get_day_of_month()}"
        )
        self.examdate_button.set_label(self.examdate)
        self.examdate_button.get_popover().popdown()

    @Gtk.Template.Callback()
    def on_csv_export_clicked(self, *args):
        file_choose_dialog = create_file_dialog(
            self,
            "Export File",
            self.lastpath,
            [
                ("CSV Files", "*.csv"),
                ("All Files", "*"),
            ],
        )
        examname = self.examname_entry.get_text()
        if examname != "":
            file_choose_dialog.set_initial_name(f"{examname}.csv")
        file_choose_dialog.save(self, None, self.export_file_cb, None)

    def export_file_cb(self, file_dialog, async_res, data):
        try:
            gfile = file_dialog.save_finish(async_res)
            filepath = Path(gfile.get_path())
            self.lastpath = filepath.parent
            self.export(filepath)
        except GLib.GError:
            # On cancel clicked
            pass

    def export(self, filepath):
        with filepath.open("w", newline="") as f:
            # TODO: Options:
            # - Delimiter
            # - float comma or dot
            # - trailing separator
            writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_NONNUMERIC)

            try:
                tab = self.grading.as_table()
                for line in tab:
                    writer.writerow(line)
            except KeyError:
                error_dialog = Gtk.AlertDialog()
                error_dialog.set_message("Error")
                error_dialog.set_detail("CSV export failed")
                error_dialog.set_modal(True)
                error_dialog.set_parent(self)
                error_dialog.show(self)
            else:
                successful_with_open_folder_dialog(
                    self, "Export successful", filepath.parent
                )

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
        self.task_list.remove(self.task_list.get_last_child())
        self.task_list.append(TaskRow(id, name, points, self.remove_task))
        add_task_row = AddTaskRow(self.add_task)
        self.task_list.append(add_task_row)
        add_task_row.taskname_entry.grab_focus()
        # self.task_list.show_all()

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
        current_obj = (
            self.task_list.get_first_child().get_next_sibling().get_next_sibling()
        )
        for _ in range(tasklist_pos):
            current_obj = current_obj.get_next_sibling()

        self.task_list.remove(current_obj)

        # self.task_list.show_all()

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
        clear_container(self.task_label_box, 0)

        for i, t in enumerate(self.tasks):
            label = Gtk.Label.new(f"T{i+1}:\n{t.name[0:12]}")
            label.set_size_request(90, -1)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_tooltip_text(f"Task {i+1}:\n{t.name}")
            self.task_label_box.append(label)
        # self.task_label_box.show_all()

    @Gtk.Template.Callback()
    def on_csv_import_clicked(self, *args):
        dialog = CsvImportDialog(self, self.csv_import_start, self.lastpath)
        dialog.present()

    @Gtk.Template.Callback()
    def on_csv_result_import_clicked(self, *args):
        dialog = CsvResultImportDialog(
            self,
            [t.name for t in self.tasks],
            self.csv_result_import_start,
            self.lastpath,
        )
        dialog.present()

    def csv_import_start(self, csv_config: CsvImportConfig):
        if self.modified:
            warn_dialog = Gtk.AlertDialog()
            warn_dialog.set_message("Warning")
            warn_dialog.set_detail("This will erase all unsaved modifications")
            warn_dialog.set_modal(True)
            warn_dialog.set_buttons(["Cancel", "Ok"])
            warn_dialog.set_cancel_button(0)
            warn_dialog.set_default_button(1)
            # warn_dialog.get_cancel_button().get_style_context().add_class("destructive-action")
            warn_dialog.choose(self, None, self.perform_csv_import, csv_config)
        else:
            self.csv_import(csv_config)

    def csv_result_import_start(self, csv_config: CsvResultImportConfig):
        if self.modified:
            warn_dialog = Gtk.AlertDialog()
            warn_dialog.set_message("Warning")
            warn_dialog.set_detail("This might overwrite existing gradings")
            warn_dialog.set_modal(True)
            warn_dialog.set_buttons(["Cancel", "Ok"])
            warn_dialog.set_cancel_button(0)
            warn_dialog.set_default_button(1)
            # warn_dialog.get_cancel_button().get_style_context().add_class("destructive-action")
            warn_dialog.choose(self, None, self.perform_csv_result_import, csv_config)
        else:
            self.csv_result_import(csv_config)

    def perform_csv_import(self, source_obj, async_res, data):
        result = source_obj.choose_finish(async_res)
        if result == 1:
            self.csv_import(data)

    def perform_csv_result_import(self, source_obj, async_res, data):
        result = source_obj.choose_finish(async_res)
        if result == 1:
            self.csv_result_import(data)

    def csv_import(self, csv_config: CsvImportConfig):
        self.grading.clear_rows()

        assert isinstance(csv_config.path, Path)

        self.lastpath = csv_config.path
        with csv_config.path.open("rb") as file:
            rawdata = file.read(100000)
        result = chardet.detect(rawdata)
        encoding = result["encoding"]

        with csv_config.path.open(newline="", encoding=encoding) as csv_f:
            csv_f.seek(0)
            assert csv_config.dialect is not None
            reader = csv.DictReader(csv_f, dialect=csv_config.dialect)
            assert isinstance(reader.fieldnames, List)
            stud_id_col = reader.fieldnames[csv_config.id_col]
            first_name_col = reader.fieldnames[csv_config.first_name_col]
            surname_col = reader.fieldnames[csv_config.surname_col]
            attempts_col = reader.fieldnames[csv_config.trial_nr_col]
            comment_col = (
                reader.fieldnames[csv_config.comment_col]
                if csv_config.comment_col is not None and csv_config.comment_col >= 0
                else None
            )
            try:
                zero_points = [Taskpoint(task.id, None) for task in self.tasks]
                for row in reader:
                    comment = row[comment_col] if comment_col is not None else None
                    stud = Student(
                        id=row[stud_id_col],
                        first_name=row[first_name_col],
                        surname=row[surname_col],
                        attempts=int(row[attempts_col]),
                        points=zero_points,
                        comment=comment,
                    )

                    self.grading.add_student(stud)

            except (ValueError, UnicodeDecodeError):
                error_dialog = Gtk.AlertDialog()
                error_dialog.set_message("Error")
                error_dialog.set_detail("Invalid Input")
                error_dialog.set_modal(True)
                error_dialog.show(self)

        self.modified = True

    def csv_result_import(self, csv_config: CsvResultImportConfig):
        assert isinstance(csv_config.path, Path)

        self.lastpath = csv_config.path
        with csv_config.path.open("rb") as file:
            rawdata = file.read(100000)
        result = chardet.detect(rawdata)
        encoding = result["encoding"]

        with csv_config.path.open(newline="", encoding=encoding) as csv_f:
            csv_f.seek(0)
            assert csv_config.dialect is not None
            reader = csv.DictReader(csv_f, dialect=csv_config.dialect)
            assert isinstance(reader.fieldnames, List)
            stud_id_col = reader.fieldnames[csv_config.id_col]
            ap_col = None
            if csv_config.ap_col is not None and csv_config.ap_col >= 0:
                ap_col = reader.fieldnames[csv_config.ap_col]
            task_mapping = {}
            for t in self.grading.tasks:
                try:
                    task_mapping[t.id] = reader.fieldnames[csv_config.columns[t.name]]
                except KeyError:
                    pass

            not_found_students = []
            for row in reader:
                stud_id = row[stud_id_col]
                try:
                    stud, grad_row = next(
                        e for e in self.grading.entries if e[0].id == stud_id
                    )
                except StopIteration:
                    not_found_students.append(stud_id)
                    continue

                for id, col in task_mapping.items():
                    try:
                        stud.points[id] = float(row[col])
                        grad_row.point_entries[int(id)].set_text(row[col])
                    except ValueError:
                        pass

                if ap_col is not None and row[ap_col] != "":
                    stud.additional_points = float(row[ap_col])
                    grad_row.additional_points_entry.set_text(row[ap_col])

            self.grading.update_point_table(self.point_table)

            if len(not_found_students) != 0:
                error_dialog = Gtk.AlertDialog()
                error_dialog.set_message("Warning")
                error_dialog.set_detail(
                    f"Couln't find the following studens: {not_found_students}"
                )
                error_dialog.set_modal(True)
                error_dialog.show(self)

        self.modified = True

    @Gtk.Template.Callback()
    def on_csv_patch_clicked(self, *args):
        self.help_menu_popover.popdown()
        dialog = CsvPatchDialog(self, self.patch_csv, self.lastpath)
        dialog.present()

    def patch_csv(self, csv_config):
        self.lastpath = csv_config.path

        with csv_config.path.open("rb") as file:
            rawdata = file.read(10000)
        result = chardet.detect(rawdata)
        encoding = result["encoding"]

        new_csv = []

        with csv_config.path.open("r", newline="", encoding=encoding) as csv_f:
            csv_f.seek(0)
            reader = csv.reader(csv_f, dialect=csv_config.dialect)

            new_csv.append(next(reader))
            for row in reader:
                try:
                    stud = self.grading.get_by_id(row[csv_config.id_col])
                    if csv_config.points_col is not None:
                        row[csv_config.points_col] = stud.total_points_final
                    if (
                        csv_config.grade_col is not None
                        and row[csv_config.grade_col]
                        == ""  # don't override existing grades
                    ):
                        if csv_config.comma_separator:
                            row[csv_config.grade_col] = stud.grade_final.replace(
                                ".", ","
                            )
                        else:
                            row[csv_config.grade_col] = stud.grade_final
                except StopIteration:
                    pass
                new_csv.append(row)

        with csv_config.path.open("w", newline="") as csv_f:
            writer = csv.writer(csv_f, dialect=csv_config.dialect)
            writer.writerows(new_csv)

    def clear_tasks(self, rebuild_gradingtable: bool = False, *args):
        # First two items are header and seperator
        clear_container(self.task_list, 2)

        self.tasks.clear()
        self.task_list.append(AddTaskRow(self.add_task))

        self.grading.update_after_clear_tasks()

        self.rebuild_gradingtable_header()

    @Gtk.Template.Callback()
    def on_save_clicked(self, widget, *args):
        file_choose_dialog = create_file_dialog(self, "Save File", self.lastpath)
        examname = self.examname_entry.get_text()
        if examname != "":
            file_choose_dialog.set_initial_name(f"{examname}.examgrades")
        file_choose_dialog.save(self, None, self.save_file_cb, None)

    def save_file_cb(self, file_dialog, async_res, data):
        try:
            gfile = file_dialog.save_finish(async_res)
            filepath = Path(gfile.get_path())
            self.lastpath = filepath.parent
            self.ask_for_pw(filepath)
        except GLib.GError:
            # On cancel clicked
            pass

    def ask_for_pw(self, filepath):
        encrypt_dialog = EncryptDialog(self, self.save, filepath)
        encrypt_dialog.present()

    def save(self, filepath: Path, password: Optional[str]):
        examname = self.examname_entry.get_text()

        save_content = create_save_content(
            examname,
            self.examdate,
            self.point_table,
            self.grading,
            self.tasks,
            password,
        )
        with filepath.open("w") as savefile:
            savefile.write(json.dumps(save_content, indent=4, sort_keys=True))

    @Gtk.Template.Callback()
    def open(self, widget, *args):
        file_choose_dialog = create_file_dialog(
            self, "Open Examgrade File", self.lastpath
        )
        file_choose_dialog.open(self, None, self.open_file_cb, None)

    def open_file_cb(self, file_dialog, async_res, data):
        if not self.clear(False):
            return
        try:
            file = file_dialog.open_finish(async_res)
            if file is not None:
                self.lastpath = Path(file.get_path()).parent
                self.load_from_file(file)
        except GLib.GError:
            # On cancel clicked
            pass

        self.set_buttons_sensitive(True)

    def load_from_file(self, file: Gio.File):
        exam = {}
        is_success, data, _tag = file.load_contents()
        if not is_success:
            error(f"can't open file {file.get_path()}")
            return

        exam = json.loads(data)
        if "Encryption" in exam["General"]:
            decrypt_dialog = DecryptDialog(self, exam, decrypt_exam, self.load_exam)
            decrypt_dialog.present()
        else:
            self.load_exam(exam)

    def load_exam(self, exam: Dict[str, Any]):
        self.set_buttons_sensitive(False)
        self.processing_revealer.set_reveal_child(True)

        try:
            tmp = self.block_histogram_update
            self.block_histogram_update = True
            self.examname_entry.set_text(exam["General"]["Name"])
            self.examdate = exam["General"]["Date"]
            if self.examdate == "":
                self.examdate_button.set_label("<Select>")
            else:
                self.examdate_button.set_label(self.examdate)

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
            self.rebuild_gradingtable_header()

            for stud in exam["Grading"]:
                self.grading.add_student(Student.from_dict(stud))
            self.update_grade_table(None, False)

            self.block_histogram_update = tmp
            self.update_histogram(None, False)
            # TODO: move to background task
            self.generate_task_plots()

        except (ValueError, TypeError):
            error_dialog = Gtk.AlertDialog()
            error_dialog.set_message("Error")
            error_dialog.set_detail("Corrupt file - aborting")
            error_dialog.set_modal(True)
            error_dialog.show(self)
            self.clear()

        self.modified = False
        self.processing_revealer.set_reveal_child(False)
        self.set_buttons_sensitive(True)
        self.redraw_visible_graphs()

    @Gtk.Template.Callback()
    def on_clear_clicked(self, widget):
        if self.modified:
            warn_dialog = Gtk.AlertDialog()
            warn_dialog.set_message("Warning")
            warn_dialog.set_detail("This will erase all unsaved modifications")
            warn_dialog.set_modal(True)
            warn_dialog.set_buttons(["Cancel", "Ok"])
            warn_dialog.set_cancel_button(0)
            warn_dialog.set_default_button(0)
            # warn_dialog.get_cancel_button().get_style_context().add_class("destructive-action")
            warn_dialog.choose(self, None, self.perform_clear, None)
        else:
            self.clear(True)

    def perform_clear(self, source_obj, async_res, data):
        result = source_obj.choose_finish(async_res)
        if result == 1:
            self.clear(True)

    def clear(self, regenerate_graphs_and_stat: bool = True) -> bool:
        """
        returns True, if the state was cleared
        """
        self.set_buttons_sensitive(False)
        self.examname_entry.set_text("")
        self.examdate = ""
        self.examdate_button.set_label("<Select>")
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

    def on_grade_table_button_pressed(self, gesture, data, x, y):
        self.grade_table_popover.set_offset(x, y)
        self.grade_table_popover.popup()

    def copy_grade_table(self, widget, data):
        self.get_clipboard().set(self.point_table.as_str())

    def switch_main_stack_setup(self, *args):
        self.main_stack.set_visible_child_name("exam_page")

    def switch_main_stack_grading(self, *args):
        self.main_stack.set_visible_child_name("grading_page")

    def switch_main_stack_results(self, *args):
        self.main_stack.set_visible_child_name("results_page")

    def switch_main_stack_graphs(self, *args):
        self.main_stack.set_visible_child_name("graphs_page")


@Gtk.Template(resource_path="/exam-grader/Add_Task_Row.ui")
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


@Gtk.Template(resource_path="/exam-grader/Task_Row.ui")
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
