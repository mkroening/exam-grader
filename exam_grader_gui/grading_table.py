from __future__ import annotations

from bisect import insort
from dataclasses import dataclass
from enum import Enum, IntEnum, unique
from typing import Any, Callable, Dict, List, Optional, Tuple

from gi.repository import Gdk, Gtk

from .exam import ExamTask, GradeState, GradeType, PointTable
from .gui_helpers import get_content


def round_points(f: float, step: float) -> float:
    return int((f + step / 2) / step) * step


def empty_cb(widget, data):
    return True


class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


@dataclass
class Taskpoint:
    task_id: int
    points: Optional[float]


@dataclass
class GradingUpdateVals:
    points: float
    points_final: float
    grade: str
    grade_final: str


class Student:
    grade: str
    grade_final: str

    def __init__(
        self,
        id: str,
        first_name: str,
        surname: str,
        attempts: int,
        points: List[Taskpoint],
        grade_calculation: Optional[
            Callable[[float, GradeType], Tuple[str, GradeState]]
        ] = None,
        additional_points: Optional[float] = None,
        grade_type: GradeType = GradeType.NOTE,
        round_points: float = 0.5,
        comment: Optional[str] = None,
    ):
        self.id = id
        self.first_name = first_name
        self.surname = surname
        self.attempts = attempts
        self.points: Dict[int, Optional[float]] = {}
        for p in points:
            self.points[p.task_id] = p.points
        self.grade_calculation = grade_calculation
        self.grade_type = grade_type
        self.additional_points = additional_points
        self.state = GradeState.PASS
        self.state_final = GradeState.PASS
        self.grade = ""
        self.grade_final = ""
        self.comment = comment
        self.round_points = round_points
        self.recalculate_points_and_grade()

    @classmethod
    def from_dict(cls, d: Dict) -> Student:
        points = []
        for id, p in d["Tasks"].items():
            try:
                points.append(Taskpoint(int(id), p))
            except ValueError:
                # Additional_Points entry is in the items as well...
                pass
        add_points = d["Tasks"].get("Additional_Points")
        comment = d.get("Comment")
        return Student(
            id=d["StudentID"],
            first_name=d["First_Name"],
            surname=d["Surname"],
            attempts=d["Attempt"],
            points=points,
            additional_points=add_points,
            grade_type=GradeType.from_shortname(d.get("GradeState", "")),
            comment=comment,
        )

    def add_task(self, new_task: ExamTask):
        self.points[new_task.id] = None

    def remove_task(self, task_id: int):
        del self.points[task_id]
        self.recalculate_points_and_grade()

    def clear_tasks(self):
        self.points.clear()

    def recalculate_points_and_grade(self) -> GradingUpdateVals:
        self.total_points = round_points(
            sum([p for p in self.points.values() if p is not None]),
            0.25,
        )
        add_points = self.additional_points
        if add_points is None:
            add_points = 0.0
        self.total_points_final = round_points(
            self.total_points + add_points, self.round_points
        )

        if self.grade_calculation is not None:
            self.grade, self.state = self.grade_calculation(
                self.total_points, self.grade_type
            )
            self.grade_final, self.state_final = self.grade_calculation(
                self.total_points_final, self.grade_type
            )
        return GradingUpdateVals(
            self.total_points, self.total_points_final, self.grade, self.grade_final
        )

    def update_state(self, new_state):
        self.state = new_state

    def update_point(self, tp: Taskpoint) -> GradingUpdateVals:
        """Updates the points of the given task. Taskid -1 is additional points"""
        if tp.task_id == -1:
            self.additional_points = tp.points
        else:
            self.points[tp.task_id] = tp.points
        return self.recalculate_points_and_grade()

    def update_comment(self, comment: str):
        if comment == "":
            self.comment = None
        else:
            self.comment = comment

    def as_dict(self) -> Dict[str, Any]:
        taskpts: Dict[str, float] = {}
        for id, p in self.points.items():
            if p is not None:
                taskpts[str(id)] = p
        if self.additional_points is not None:
            taskpts["Additional_Points"] = self.additional_points
        d = {
            "StudentID": self.id,
            "First_Name": self.first_name,
            "Surname": self.surname,
            "Attempt": self.attempts,
            "GradeState": self.grade_type.shortname(),
            "Tasks": taskpts,
        }
        if self.comment is not None:
            d["Comment"] = self.comment
        return d

    def as_list(self) -> List[str]:
        l = [self.id, self.first_name, self.surname, str(self.attempts)]
        l += list(map(str, self.points.values()))
        l += [str(self.additional_points)]
        l += [
            str(self.total_points),
            str(self.total_points_final),
            self.grade,
            self.grade_final,
        ]
        comment_str = self.comment or ""
        l.append(
            comment_str.replace("\n", " ")
        )  # We don't include newlines in the CSV export. It will most likely break stuff.
        return l

    def __lt__(self, other: Student):
        return self.id < other.id


class GradeTable:
    def __init__(
        self,
        tasks: List[ExamTask],
        point_table: PointTable,
        listbox: Gtk.ListBox,
        entry_changed_cb: Callable,
    ):
        """tasks and point_table are references to existing data and it is relied on them to persist/update during the lifetime of this object"""
        self.tasks = tasks
        self.entries: List[Tuple[Student, GradingRow]] = []
        self.point_table = point_table
        self.listbox = listbox
        self.grading_liststore = GradeType.as_liststore()
        self.entry_changed_cb = entry_changed_cb

    def add_student(self, stud: Student):
        stud.grade_calculation = self.point_table.grade
        stud.round_points = self.point_table.min_step
        row = GradingRow(
            stud,
            self.tasks,
            self.grading_liststore,
            self.entry_changed_cb,
            self.delete_row,
            self.focus_next_row,
            self.focus_other_entry,
        )
        insort(self.entries, (stud, row))
        self.listbox.append(row)

    def focus_next_row(self, widget, row):
        try:
            self.get_valid_row(row, direction=Direction.DOWN).focus_on_entry(
                self.tasks[0].id
            )
        except AttributeError:
            pass

    def focus_other_entry(self, row, task_id: int, direction: Direction):
        focus_row = row
        if direction == Direction.UP or direction == Direction.DOWN:
            focus_row = self.get_valid_row(row, direction)

        current_task_index = self.get_task_index(task_id)
        if direction == Direction.LEFT:
            current_task_index -= 1
        if direction == Direction.RIGHT:
            current_task_index += 1
        focus_id = (
            self.tasks[current_task_index].id
            if current_task_index < len(self.tasks) and current_task_index != -1
            # -1 is the additional points entry
            else -1
        )
        if focus_row is not None and focus_id is not None:
            focus_row.focus_on_entry(focus_id)

    def get_valid_row(self, row, direction: Direction) -> Optional[GradingRow]:
        current_row = (
            # Find current row index
            next(i for i, r in enumerate(self.listbox) if r.get_child() == row)
            - 2
        )
        if direction == Direction.DOWN:
            next_row_nr = current_row + 1
        elif direction == Direction.UP:
            next_row_nr = current_row - 1
        else:
            raise RuntimeError("Can only find Up/Down with this function")

        while next_row_nr < len(self.entries) and next_row_nr >= 0:
            if self.entries[next_row_nr][0].grade_type.is_counted():
                next_row = self.listbox.get_row_at_index(next_row_nr + 2).get_child()
                assert isinstance(next_row, GradingRow)
                return next_row
            if direction == Direction.DOWN:
                next_row_nr += 1
            elif direction == Direction.UP:
                next_row_nr -= 1
            else:
                raise RuntimeError("Can only find Up/Down with this function")

        return None

    def delete_row(self, widget, id: int):
        # Skip the first two rows as they are headers
        current_row = (
            self.listbox.get_first_child().get_next_sibling().get_next_sibling()
        )
        while current_row is not None:
            next_row = current_row.get_next_sibling()
            if current_row.get_child().id == id:
                self.listbox.remove(current_row)
                break
            current_row = next_row

        pos = next(i for i, e in enumerate(self.entries) if e[0].id == id)
        del self.entries[pos]
        self.entry_changed_cb()

    def clear_rows(self):
        self.entries.clear()

        # First two items are header and seperator
        current_row = (
            self.listbox.get_first_child().get_next_sibling().get_next_sibling()
        )
        while current_row is not None:
            next_row = current_row.get_next_sibling()
            self.listbox.remove(current_row)
            current_row = next_row

    def add_clicked(self, id: str, first_name: str, surname: str, attempts: int):
        zero_points = [Taskpoint(task.id, None) for task in self.tasks]
        stud = Student(id, first_name, surname, attempts, zero_points)
        self.add_student(stud)

    def update_after_add_task(self, new_task: ExamTask):
        """update student's tasks"""
        # self.tasks.append(new_task)
        for stud, row in self.entries:
            stud.add_task(new_task)
            row.update_entries()

    def update_after_remove_task(self, task_id: int):
        # self.tasks.remove(self.tasks[task_id])
        for stud, row in self.entries:
            stud.remove_task(task_id)
            row.update_entries()

    def update_after_clear_tasks(self):
        for stud, row in self.entries:
            stud.clear_tasks()
            row.update_entries()
        # self.tasks.clear()

    def update_point_table(self, pt: PointTable):
        self.point_table = pt
        for stud, row in self.entries:
            stud.grade_calculation = self.point_table.grade
            updated_grades = stud.recalculate_points_and_grade()
            row.set_points_from_update_vals(updated_grades)
            row.update_grade_style()

    def grade_histogram(self) -> Dict[str, int]:
        hist = {}
        for label in self.point_table.all_labels:
            hist[label] = 0
        for stud, _row in self.entries:
            # try:
            hist[stud.grade_final] += 1
            # except KeyError:
            #     pass
        return hist

    def point_histogram(self, point_step: float = 0.5) -> Dict[str, int]:
        hist = {}
        for label in range(int(self.point_table.points_maximum / point_step + 1.0)):
            hist[str(label / (1 / point_step))] = 0
        for stud, _row in self.entries:
            if stud.grade_type.is_counted():
                try:
                    hist[str(stud.total_points_final)] += 1
                except KeyError:
                    pass
        return hist

    def task_histogram_and_points(
        self, task_id: int, point_step: float = 0.25
    ) -> Tuple[Dict[float, int], List[float]]:
        hist = {}
        pts = []
        task = next(t for t in self.tasks if t.id == task_id)
        for label in range(int(task.max_points / point_step + 1.0)):
            hist[float(label / (1 / point_step))] = 0
        for stud, _row in self.entries:
            if stud.grade_type.is_counted():
                p = stud.points.get(task_id)
                if p is not None:
                    pts.append(p)
                    hist[p] += 1
        return hist, pts

    def point_and_grades_list(self) -> Tuple[List[float], List[str]]:
        """Returns a list of all grades and points of exams that are counted for statistic reasons"""
        points = []
        grades = []
        for stud, _row in self.entries:
            if stud.grade_type.is_counted():
                grades.append(stud.grade_final)
                points.append(stud.total_points_final)

        return (points, grades)

    def export(self) -> List[Dict[str, Any]]:
        exp = []
        for stud, _row in self.entries:
            exp.append(stud.as_dict())
        return exp

    def as_table(self) -> List[List[str]]:
        tab = []
        header = ["STUDENT_ID", "FIRST_NAME", "FAMILY_NAME", "ATTEMPTS"]
        for t in self.tasks:
            header += [t.name.upper()]
        header += [
            "ADDITIONAL_POINTS",
            "TOTAL_POINTS",
            "TOTAL_POINTS_FINAL",
            "GRADE",
            "GRADE_FINAL",
            "COMMENT",
        ]
        tab.append(header)
        for stud, _row in self.entries:
            tab.append(stud.as_list())
        return tab

    def get_task_index(self, task_id: int) -> int:
        try:
            return next((i, t) for i, t in enumerate(self.tasks) if t.id == task_id)[0]
        except StopIteration:
            return -1

    def get_by_id(self, id: str) -> Student:
        return next(e[0] for e in self.entries if e[0].id == id)


@Gtk.Template(resource_path="/exam-grader/Add_Grading_Row.ui")
class AddGradingRow(Gtk.Box):
    __gtype_name__ = "add_grading_row"
    id_entry = Gtk.Template.Child("id_entry")
    first_name_entry = Gtk.Template.Child("first_name_entry")
    surname_entry = Gtk.Template.Child("surname_entry")
    attempts_entry = Gtk.Template.Child("attempts_entry")
    add_button = Gtk.Template.Child("add_button")

    def __init__(self, grading: GradeTable):
        super(Gtk.Box, self).__init__()
        self.grading = grading

    def clear(self):
        self.id_entry.set_text("")
        self.first_name_entry.set_text("")
        self.surname_entry.set_text("")
        self.attempts_entry.set_text("")

    @Gtk.Template.Callback()
    def on_entry_changed(self, widget):
        def entry_unique(txt):
            return txt not in map(lambda e: e[0].id, self.grading.entries)

        self.id = get_content(self.id_entry, str, entry_unique)
        self.first_name = get_content(self.first_name_entry, str)
        self.surname = get_content(self.surname_entry, str)
        self.attempts = get_content(self.attempts_entry, int)
        correct_vals = (
            self.id is not None
            and self.first_name is not None
            and self.surname is not None
            and self.attempts is not None
        )
        self.add_button.set_sensitive(correct_vals)

    @Gtk.Template.Callback()
    def on_activate(self, widget):
        if self.add_button.get_sensitive():
            self.on_add_clicked(widget)

    @Gtk.Template.Callback()
    def on_add_clicked(self, widget):
        self.grading.add_clicked(self.id, self.first_name, self.surname, self.attempts)
        self.clear()


@Gtk.Template(resource_path="/exam-grader/Grading_Row.ui")
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
    state_combo = Gtk.Template.Child("state_combo")
    comment_buffer = Gtk.Template.Child("comment_buffer")
    delete_button = Gtk.Template.Child("delete_button")

    additional_points_entry = Gtk.Template.Child("additional_points_entry")

    def __init__(
        self,
        stud: Student,
        tasks: List[ExamTask],
        examstates: Gtk.ListStore,
        row_changed_cb: Callable,
        row_deleted_cb: Callable,
        next_row_cb: Callable,
        focus_other_entry_cb: Callable,
    ):
        super(Gtk.Box, self).__init__()

        self.id = stud.id
        self.student = stud
        self.tasks = tasks
        self.row_changed_cb = row_changed_cb
        self.student_id_label.set_text(stud.id)
        self.first_name_label.set_text(stud.first_name)
        self.surname_label.set_text(stud.surname)
        self.trials_label.set_text(str(stud.attempts))
        if stud.attempts > 2:
            self.trials_label.get_style_context().add_class("warning")

        self.delete_button.connect("clicked", row_deleted_cb, self.id)

        combo_entry = self.state_combo.get_child()
        combo_entry.set_hexpand(False)
        combo_entry.set_hexpand_set(True)
        combo_entry.set_max_width_chars(3)
        self.state_combo.set_model(examstates)
        self.state_combo.set_active(self.student.grade_type)

        self.state_combo.connect("changed", self.on_combo_change)
        # Disable the Mouse scroll, to avoid unintentional changes
        # TODO
        # self.state_combo.connect("scroll_event", empty_cb)

        self.point_entries = {}

        keycont = Gtk.EventControllerKey.new()
        keycont.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keycont.connect("key-pressed", self.key_pressed, -1)
        self.additional_points_entry.add_controller(keycont)
        self.additional_points_entry.connect("changed", self.on_entry_update, -1)
        self.additional_points_entry.connect("activate", next_row_cb, self)
        if stud.additional_points is not None:
            self.additional_points_entry.set_text(str(stud.additional_points))

        for t in self.tasks:
            points = stud.points.get(t.id, None)
            taskpoint_entry = self.new_entry(t.id, points, t.max_points)
            self.point_entries[t.id] = taskpoint_entry
            self.task_point_area.append(taskpoint_entry)

        self.set_dim_entries(not (self.student.grade_type.is_counted()))

        if stud.comment is not None:
            self.comment_buffer.set_text(stud.comment)
        self.comment_buffer.connect("changed", self.on_comment_changed)

        self.focus_other_entry_cb = focus_other_entry_cb

    def next_entry_grab_focus(self, widget, data):
        next_entry = None
        try:
            task_nr = next(i for i, t in enumerate(self.tasks) if t.id == data)
            next_entry = self.point_entries[self.tasks[task_nr + 1].id]
        except (StopIteration, IndexError):
            next_entry = self.additional_points_entry
        next_entry.grab_focus()

    def focus_on_entry(self, task_id: int):
        next_entry = None
        try:
            next_entry = self.point_entries[task_id]
        except KeyError:
            next_entry = self.additional_points_entry
        next_entry.grab_focus()

    def new_entry(
        self, taskid: int, points: Optional[float], max_points: float
    ) -> Gtk.Entry:
        taskpoint_entry = Gtk.Entry()
        taskpoint_entry.set_size_request(90, -1)
        taskpoint_entry.set_placeholder_text("")
        taskpoint_entry.set_hexpand(False)
        taskpoint_entry.set_hexpand_set(True)
        taskpoint_entry.set_vexpand(False)
        taskpoint_entry.set_vexpand_set(True)
        taskpoint_entry.set_max_width_chars(5)
        taskpoint_entry.set_alignment(0.5)
        taskpoint_entry.set_width_chars(3)
        if points is not None:
            taskpoint_entry.set_text(str(points))
            taskpoint_entry.set_progress_fraction(points / max_points)
        taskpoint_entry.connect("activate", self.next_entry_grab_focus, taskid)
        taskpoint_entry.connect("changed", self.on_entry_update, taskid)
        taskpoint_entry.get_style_context().add_class("flat")
        keycont = Gtk.EventControllerKey.new()
        keycont.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keycont.connect("key-pressed", self.key_pressed, taskid)
        taskpoint_entry.add_controller(keycont)
        return taskpoint_entry

    def key_pressed(self, conroller, keyval, keycode, state, taskid):
        """Provide Arrow key navigation"""
        if keyval == Gdk.keyval_from_name("Up"):
            self.focus_other_entry_cb(self, taskid, Direction.UP)
            return True
        if keyval == Gdk.keyval_from_name("Down"):
            self.focus_other_entry_cb(self, taskid, Direction.DOWN)
            return True
        if (
            keyval == Gdk.keyval_from_name("Left")
            and "GDK_CONTROL_MASK" in state.value_names
        ):
            self.focus_other_entry_cb(self, taskid, Direction.LEFT)
            return True
        if (
            keyval == Gdk.keyval_from_name("Right")
            and "GDK_CONTROL_MASK" in state.value_names
        ):
            self.focus_other_entry_cb(self, taskid, Direction.RIGHT)
            return True
        return False

    def update_entries(self):
        """Update the row, after the tasks and the student are already updated"""
        # remove not anymore existing tasks
        remove_vals = []
        for t_id in self.point_entries.keys():
            try:
                next(t for t in self.tasks if t.id == t_id)
            except StopIteration:
                remove_vals.append(t_id)
        for v in remove_vals:
            self.task_point_area.remove(self.point_entries[v])
            del self.point_entries[v]

        # add not yet existing tasks
        for _i, t in enumerate(self.tasks):
            if self.point_entries.get(t.id) is None:
                new_e = self.new_entry(t.id, self.student.points[t.id], t.max_points)
                self.point_entries[t.id] = new_e
                self.task_point_area.append(new_e)

        new_vals = self.student.recalculate_points_and_grade()
        self.set_points_from_update_vals(new_vals)

    def set_point_labels(
        self,
        total_points: float,
        total_points_final: float,
        grade: str,
        grade_final: str,
    ):
        self.total_points_label.set_text(str(total_points))
        self.total_points_final_label.set_text(str(total_points_final))
        self.grade_label.set_text(str(grade))
        self.grade_final_label.set_text(str(grade_final))

    def set_points_from_update_vals(self, update_vals=GradingUpdateVals):
        self.set_point_labels(
            update_vals.points,
            update_vals.points_final,
            update_vals.grade,
            update_vals.grade_final,
        )

    def set_dim_entries(self, dim: bool):
        self.student_id_label.set_sensitive(not dim)
        self.first_name_label.set_sensitive(not dim)
        self.surname_label.set_sensitive(not dim)
        self.trials_label.set_sensitive(not dim)
        self.total_points_label.set_sensitive(not dim)
        self.total_points_final_label.set_sensitive(not dim)
        self.grade_label.set_sensitive(not dim)
        self.grade_final_label.set_sensitive(not dim)
        for entry in self.point_entries.values():
            entry.set_sensitive(not dim)
        self.additional_points_entry.set_sensitive(not dim)

    def update_grade_style(self):
        if self.student.state == GradeState.FAIL:
            self.grade_label.get_style_context().add_class("error")
        else:
            self.grade_label.get_style_context().remove_class("error")
        if self.student.state_final == GradeState.FAIL:
            self.grade_final_label.get_style_context().add_class("error")
            if self.student.attempts > 2:
                self.first_name_label.get_style_context().add_class("error")
                self.surname_label.get_style_context().add_class("error")
        else:
            self.grade_final_label.get_style_context().remove_class("error")
            self.first_name_label.get_style_context().remove_class("error")
            self.surname_label.get_style_context().remove_class("error")

    def on_entry_update(self, widget, task_id: int):
        p = None

        def non_negative(f: float) -> bool:
            return f >= 0

        if task_id == -1:
            # Additional Point entry
            entry = self.additional_points_entry
            p = get_content(entry, float, non_negative, default_val=None)
        else:
            entry = self.point_entries[task_id]
            task = next(t for t in self.tasks if t.id == task_id)

            def validate_points(points):
                return points <= task.max_points and non_negative(points)

            p = get_content(entry, float, validate_points, default_val=None)
            if p is not None:
                entry.set_progress_fraction(p / task.max_points)

        new_vals = self.student.update_point(Taskpoint(task_id, p))
        self.set_points_from_update_vals(new_vals)
        self.update_grade_style()
        self.row_changed_cb()

    def on_combo_change(self, widget):
        active = self.state_combo.get_active()
        if active == -1:
            print("-1 active")
            active = 0
        self.student.grade_type = GradeType(active)
        new_vals = self.student.recalculate_points_and_grade()
        self.set_points_from_update_vals(new_vals)
        self.set_dim_entries(not (self.student.grade_type.is_counted()))
        self.update_grade_style()
        self.row_changed_cb()

    def on_comment_changed(self, widget):
        self.student.update_comment(
            widget.get_text(widget.get_start_iter(), widget.get_end_iter(), True)
        )


@unique
class SortKeys(IntEnum):
    ID = 0
    FIRST_NAME = 1
    SURNAME = 2
    ATTEMPTS = 3
    POINTS = 4

    def as_str(self) -> str:
        return SortKeys.names()[self]

    @classmethod
    def names(cls) -> List[str]:
        return ["ID", "First Name", "Surname", "Attempts", "Points"]

    @classmethod
    def as_liststore(cls) -> Gtk.ListStore:
        liststore = Gtk.ListStore(str)
        for n in cls.names():
            liststore.append([n])
        return liststore


def grading_row_sort_func(row_1, row_2, data: SortKeys, notify_destroy):
    # True: Swap
    # False: Keep

    c1 = row_1.get_child()
    c2 = row_2.get_child()

    if type(c1) == Gtk.Separator:
        if type(c2) == Gtk.Box:
            return True
        if type(c2) == GradingRow:
            return False

    if type(c1) == Gtk.Box:
        return False

    if type(c1) == GradingRow:
        if type(c2) == Gtk.Box:
            return True
        if type(c2) == Gtk.Separator:
            return True
        if type(c2) == GradingRow:
            if data == SortKeys.ID:
                return c1.id > c2.id
            elif data == SortKeys.FIRST_NAME:
                return c1.student.first_name > c2.student.first_name
            elif data == SortKeys.SURNAME:
                return c1.student.surname > c2.student.surname
            elif data == SortKeys.ATTEMPTS:
                return c1.student.attempts < c2.student.attempts
            elif data == SortKeys.POINTS:
                return c1.student.total_points_final < c2.student.total_points_final

    print(f"Warning: Unknown list row comparison: {type(c1)} - {type(c2)}")
    return False


def grading_row_filter_func(row, text: str, notify_destroy):
    c = row.get_child()
    if type(c) == Gtk.Separator or type(c) == Gtk.Box:
        return True
    assert type(c) == GradingRow
    t = text.lower()
    if (
        t in c.id.lower()
        or t in c.student.first_name.lower()
        or t in c.student.surname.lower()
    ):
        return True
    return False
