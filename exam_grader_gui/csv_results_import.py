import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Dict, List

from gi.repository import GLib, Gtk

from .gui_helpers import create_file_dialog, show_message_dialog


@dataclass
class CsvResultImportConfig:
    path: Optional[Path]
    dialect: Optional[csv.Dialect]
    columns: Dict[str, int]
    id_col: int
    ap_col: Optional[int]

    def is_valid(self) -> bool:
        selections = set()
        if self.id_col != -1:
            selections.add(self.id_col)
        if len(self.columns) == 0 and self.ap_col == -1:
            return False
        for idx in self.columns.values():
            if idx != -1:
                selections.add(idx)
        nr_combos = 1 + len(self.columns)
        if self.ap_col != -1 and self.ap_col is not None:
            selections.add(self.ap_col)
            nr_combos += 1
        return len(selections) == nr_combos and self.path is not None


@Gtk.Template(resource_path="/exam-grader/Csv_Import_Grades.ui")
class CsvResultImportDialog(Gtk.Window):
    __gtype_name__ = "csv_result_import_dialog"

    select_file_button = Gtk.Template.Child("select_file_button")
    csv_col_selection_revealer = Gtk.Template.Child("csv_col_selection_revealer")
    stud_id_combo = Gtk.Template.Child("stud_id_combo")
    combo_grid = Gtk.Template.Child("combo_grid")
    cancel_button = Gtk.Template.Child("cancel_button")
    import_button = Gtk.Template.Child("import_button")

    def __init__(
        self,
        parent,
        tasks: List[str],
        import_callback: Callable[[CsvResultImportConfig], None],
        lastdir: Optional[str] = None,
    ):
        super(Gtk.Window, self).__init__()
        self.set_transient_for(parent)
        # self.set_modal(parent)
        self.import_callback = import_callback
        self.lastdir = lastdir
        self.tasks = tasks
        self.combos: Dict[str, Gtk.ComboBoxText] = {}

        self.ap_label = Gtk.Label.new("Additional Points")
        self.ap_comb = Gtk.ComboBoxText.new()
        self.ap_comb.connect("changed", self.on_combo_changed)

        self.csv_config = CsvResultImportConfig(None, None, {}, -1, -1)

    @Gtk.Template.Callback()
    def on_select_file_clicked(self, widget):
        file_choose_dialog = create_file_dialog(
            self,
            "Import CSV File",
            self.lastdir,
            [
                ("CSV Files", "*.csv"),
                ("All Files", "*"),
            ],
        )
        file_choose_dialog.open(self, None, self.on_file_set, None)

    def on_file_set(self, file_dialog, async_res, data):
        try:
            file = file_dialog.open_finish(async_res)
            if file is not None:
                self.csv_config.path = Path(file.get_path())
                filename = self.csv_config.path.parts[-1]
                if len(filename) > 30:
                    filename = filename[0:18] + "..." + filename[-10:-1]
                self.select_file_button.set_label(filename)

            else:
                return
        except GLib.GError:
            # On cancel clicked
            return

        with self.csv_config.path.open(newline="") as csv_f:
            if csv.Sniffer().has_header(csv_f.read(50000)):
                csv_f.seek(0)
                self.csv_config.dialect = csv.Sniffer().sniff(csv_f.read(100000))
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=self.csv_config.dialect)
                model = Gtk.ListStore(str)
                model_with_empty = Gtk.ListStore(str)
                model_with_empty.append([])

                for name in filter(
                    lambda name: name != "",
                    map(lambda name: name.strip(), reader.fieldnames),
                ):
                    entry = [name]
                    model.append(entry)
                    model_with_empty.append(entry)

                def search_keyword(keywords) -> int:
                    for i, s in enumerate(reader.fieldnames):
                        for kw in keywords:
                            if s.upper().find(kw.upper()) != -1:
                                return i
                    return 0

                self.stud_id_combo.set_model(model)
                combo_index = search_keyword(
                    ["MATRIK", "REGISTRATION", "STUDENT_ID", "IDENTIFIER"]
                )
                self.stud_id_combo.set_active(combo_index)

                self.combos = {}
                for i, task in enumerate(self.tasks):
                    new_label = Gtk.Label.new(task)
                    self.combo_grid.attach(new_label, 0, i + 1, 1, 1)
                    new_comb = Gtk.ComboBoxText.new()
                    new_comb.set_model(model_with_empty)
                    new_comb.connect("changed", self.on_combo_changed)
                    self.combo_grid.attach(new_comb, 1, i + 1, 1, 1)

                    self.combos[task] = new_comb

                self.combo_grid.attach(self.ap_label, 0, len(self.combos) + 1, 1, 1)
                self.ap_comb.set_model(model_with_empty)
                self.combo_grid.attach(self.ap_comb, 1, len(self.combos) + 1, 1, 1)

                self.csv_col_selection_revealer.set_reveal_child(True)
                # Very dirty hack, but with out this, the window glitches
                self.set_visible(False)
                self.set_visible(True)
            else:
                show_message_dialog(
                    self, "Invalid CSV", "Ensure that the CSV has a header row"
                )

    @Gtk.Template.Callback()
    def on_combo_changed(self, widget):
        self.csv_config.id_col = self.stud_id_combo.get_active()
        self.csv_config.ap_col = self.ap_comb.get_active() - 1
        self.csv_config.columns = {}
        for task in self.tasks:
            try:
                selected_col = self.combos[task].get_active() - 1
                if selected_col >= 0:
                    self.csv_config.columns[task] = selected_col
            except KeyError:
                self.import_button.set_sensitive(False)
                return

        self.import_button.set_sensitive(self.csv_config.is_valid())

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.destroy()

    @Gtk.Template.Callback()
    def on_import_clicked(self, widget):
        self.import_callback(self.csv_config)
        self.destroy()
