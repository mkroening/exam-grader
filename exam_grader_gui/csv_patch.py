import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import chardet
from gi.repository import GLib, Gtk

from .gui_helpers import create_file_dialog


@dataclass
class CsvPatchConfig:
    path: Optional[Path]
    dialect: Optional[csv.Dialect]
    id_col: int
    points_col: Optional[int]
    grade_col: Optional[int]
    comma_separator: bool

    def is_valid(self) -> bool:
        return (
            self.id_col != -1
            and self.path is not None
            and (self.points_col is not None or self.grade_col is not None)
        )


@Gtk.Template(resource_path="/exam-grader/Csv_Patch_Dialog.ui")
class CsvPatchDialog(Gtk.Window):
    __gtype_name__ = "csv_patch_dialog"

    select_file_button = Gtk.Template.Child("select_file_button")
    csv_col_selection_revealer = Gtk.Template.Child("csv_col_selection_revealer")
    stud_id_combo = Gtk.Template.Child("stud_id_combo")
    points_combo = Gtk.Template.Child("points_combo")
    grade_combo = Gtk.Template.Child("grade_combo")
    separator_combo = Gtk.Template.Child("separator_combo")
    # cancel_button = Gtk.Template.Child("cancel_button")
    patch_button = Gtk.Template.Child("patch_button")
    quote_toggle_button = Gtk.Template.Child("quote_toggle_button")

    def __init__(
        self,
        parent,
        patch_callback: Callable[[CsvPatchConfig], None],
        lastdir: Optional[str] = None,
    ):
        super(Gtk.Window, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)
        self.patch_callback = patch_callback
        self.lastdir = lastdir
        self.csv_config = CsvPatchConfig(None, None, -1, None, None, False)

    @Gtk.Template.Callback()
    def on_select_file_clicked(self, _widget):
        file_choose_dialog = create_file_dialog(
            self,
            "Select CSV File",
            self.lastdir,
            [
                ("CSV Files", "*.csv"),
                ("All Files", "*"),
            ],
        )
        file_choose_dialog.open(self, None, self.on_file_set, None)

    def on_file_set(self, file_dialog, async_res, _data):
        try:
            file = file_dialog.open_finish(async_res)
            if file is not None:
                self.csv_config.path = Path(file.get_path())
                self.lastdir = self.csv_config.path
                filename = self.csv_config.path.parts[-1]
                if len(filename) > 30:
                    filename = filename[0:18] + "..." + filename[-10:-1]
                self.select_file_button.set_label(filename)

            else:
                return
        except GLib.GError:
            # On cancel clicked
            return

        self.patch_button.set_sensitive(False)

        with self.csv_config.path.open("rb") as file:
            rawdata = file.read()
        result = chardet.detect(rawdata)
        encoding = result["encoding"]

        with self.csv_config.path.open(newline="", encoding=encoding) as csv_f:
            try:
                if csv.Sniffer().has_header(csv_f.read(1024)):
                    csv_f.seek(0)
                    # TODO: make delimiter variable
                    self.csv_config.dialect = csv.Sniffer().sniff(csv_f.read(1024))

                    csv_f.seek(0)
                    reader = csv.DictReader(csv_f, dialect=self.csv_config.dialect)
                    model = Gtk.ListStore(str)
                    model_with_empty = Gtk.ListStore(str)
                    model_with_empty.append(["<Ignore>"])

                    for name in filter(
                        lambda name: name != "",
                        map(lambda name: name.strip(), reader.fieldnames),
                    ):
                        model.append(
                            [
                                name,
                            ]
                        )
                        model_with_empty.append(
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
                    combo_index = search_keyword(
                        ["MATRIK", "REGISTRATION", "STUDENT_ID"]
                    )
                    self.stud_id_combo.set_active(combo_index)

                    self.points_combo.set_model(model_with_empty)
                    combo_index = search_keyword(["POINT"])
                    if combo_index != 0:
                        combo_index += 1
                    self.points_combo.set_active(combo_index)
                    self.grade_combo.set_model(model_with_empty)
                    combo_index = search_keyword(["GRADE"])
                    if combo_index != 0:
                        combo_index += 1
                    self.grade_combo.set_active(combo_index)

                    csv_f.seek(0)
                    if csv_f.read(1) == '"':
                        self.quote_toggle_button.set_active(True)
                    if self.separator_combo.get_active() == -1:
                        self.separator_combo.set_active(0)
                    self.csv_col_selection_revealer.set_reveal_child(True)
                else:
                    raise RuntimeError("Unimplemented")
            except (UnicodeDecodeError, csv.Error):
                self.select_file_button.set_label("<select file>")
                self.csv_col_selection_revealer.set_reveal_child(False)
                self.patch_button.set_sensitive(False)

                error_dialog = Gtk.AlertDialog()
                error_dialog.set_message("Error")
                error_dialog.set_detail("Invalid Input")
                error_dialog.set_modal(True)
                error_dialog.show(self)
                return

    @Gtk.Template.Callback()
    def on_combo_changed(self, widget):
        self.csv_config.id_col = self.stud_id_combo.get_active()

        col = self.points_combo.get_active() - 1
        if col < 0:
            self.csv_config.points_col = None
        else:
            self.csv_config.points_col = col

        col = self.grade_combo.get_active() - 1
        if col < 0:
            self.csv_config.grade_col = None
        else:
            self.csv_config.grade_col = col

        self.csv_config.comma_separator = self.separator_combo.get_active() == 0
        self.patch_button.set_sensitive(self.csv_config.is_valid())

    @Gtk.Template.Callback()
    def on_quote_toggle(self, widget):
        if self.quote_toggle_button.get_active():
            self.csv_config.dialect.quoting = csv.QUOTE_ALL
        else:
            self.csv_config.dialect.quoting = csv.QUOTE_NONE

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.destroy()

    @Gtk.Template.Callback()
    def on_patch_clicked(self, widget):
        self.destroy()
        self.patch_callback(self.csv_config)
