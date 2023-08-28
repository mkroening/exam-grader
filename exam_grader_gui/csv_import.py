import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from gi.repository import GLib, Gtk

from .gui_helpers import create_file_dialog


@dataclass
class CsvImportConfig:
    path: Optional[Path]
    dialect: Optional[csv.Dialect]
    id_col: int
    first_name_col: int
    surname_col: int
    trial_nr_col: int

    def is_valid(self) -> bool:
        selections = set()
        for idx in [
            self.id_col,
            self.first_name_col,
            self.surname_col,
            self.trial_nr_col,
        ]:
            if idx != -1:
                selections.add(idx)
        return len(selections) == 4 and self.path is not None


@Gtk.Template(resource_path="/exam-grader/Csv_Import_Dialog.ui")
class CsvImportDialog(Gtk.Window):
    __gtype_name__ = "csv_import_dialog"

    select_file_button = Gtk.Template.Child("select_file_button")
    csv_col_selection_revealer = Gtk.Template.Child("csv_col_selection_revealer")
    stud_id_combo = Gtk.Template.Child("stud_id_combo")
    first_name_combo = Gtk.Template.Child("first_name_combo")
    surname_combo = Gtk.Template.Child("surname_combo")
    trial_nr_combo = Gtk.Template.Child("trial_nr_combo")
    cancel_button = Gtk.Template.Child("cancel_button")
    import_button = Gtk.Template.Child("import_button")

    def __init__(
        self,
        parent,
        import_callback: Callable[[CsvImportConfig], None],
        lastdir: Optional[str] = None,
    ):
        super(Gtk.Window, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)
        self.import_callback = import_callback
        self.lastdir = lastdir

        self.csv_config = CsvImportConfig(None, None, -1, -1, -1, -1)

        # if lastdir is not None:
        #     self.select_file_button.set_label(lastdir)

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
                self.select_file_button.set_label(self.csv_config.path.parts[-1]
)

            else:
                return
        except GLib.GError:
            # On cancel clicked
            return

        with self.csv_config.path.open(newline="") as csv_f:
            if csv.Sniffer().has_header(csv_f.read(1024)):
                self.csv_config.dialect = csv.Sniffer().sniff(csv_f.read(1024))
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=self.csv_config.dialect)
                model = Gtk.ListStore(str)

                for name in filter(
                    lambda name: name != "",
                    map(lambda name: name.strip(), reader.fieldnames),
                ):
                    model.append(
                        [
                            name,
                        ]
                    )

                def search_keyword(keywords) -> int:
                    for i, s in enumerate(reader.fieldnames):
                        for kw in keywords:
                            if s.find(kw) != -1:
                                return i
                    return 0

                self.stud_id_combo.set_model(model)
                combo_index = search_keyword(["MATRIK", "REGISTRATION", "STUDENT_ID"])
                self.stud_id_combo.set_active(combo_index)
                self.first_name_combo.set_model(model)
                combo_index = search_keyword(["FIRST_NAME", "VORNAME"])
                self.first_name_combo.set_active(combo_index)
                self.surname_combo.set_model(model)
                combo_index = search_keyword(
                    ["SURNAME", "FAMILY_NAME", "LAST_NAME", "NACHNAME"]
                )
                self.surname_combo.set_active(combo_index)
                self.trial_nr_combo.set_model(model)
                combo_index = search_keyword(["TRIAL", "ANTRITTE"])
                self.trial_nr_combo.set_active(combo_index)
                self.csv_col_selection_revealer.set_reveal_child(True)
            else:
                raise RuntimeError("Unimplemented")

    @Gtk.Template.Callback()
    def on_combo_changed(self, widget):
        self.csv_config.id_col = self.stud_id_combo.get_active()
        self.csv_config.first_name_col = self.first_name_combo.get_active()
        self.csv_config.surname_col = self.surname_combo.get_active()
        self.csv_config.trial_nr_col = self.trial_nr_combo.get_active()
        self.import_button.set_sensitive(self.csv_config.is_valid())

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.destroy()

    @Gtk.Template.Callback()
    def on_import_clicked(self, widget):
        self.import_callback(self.csv_config)
        self.destroy()
