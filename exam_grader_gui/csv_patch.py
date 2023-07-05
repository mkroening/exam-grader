import csv
from pathlib import Path
from typing import Optional

import chardet
from gi.repository import Gtk


@Gtk.Template(resource_path="/exam-grader/Csv_Patch_Dialog.glade")
class CsvPatchDialog(Gtk.Dialog):
    __gtype_name__ = "csv_patch_dialog"

    csv_chooser = Gtk.Template.Child("csv_chooser")
    csv_col_selection_revealer = Gtk.Template.Child("csv_col_selection_revealer")
    stud_id_combo = Gtk.Template.Child("stud_id_combo")
    points_combo = Gtk.Template.Child("points_combo")
    grade_combo = Gtk.Template.Child("grade_combo")
    separator_combo = Gtk.Template.Child("separator_combo")
    cancel_button = Gtk.Template.Child("cancel_button")
    patch_button = Gtk.Template.Child("patch_button")
    quote_toggle_button = Gtk.Template.Child("quote_toggle_button")

    def __init__(self, parent, lastdir: Optional[str] = None):
        super(Gtk.Dialog, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)
        if lastdir is not None:
            self.csv_chooser.set_current_folder(lastdir)

    @Gtk.Template.Callback()
    def on_file_set(self, widget):
        self.patch_button.set_sensitive(False)
        filename = self.csv_chooser.get_filename()
        self.csv = Path(filename)

        with self.csv.open("rb") as file:
            rawdata = file.read(1000)
        result = chardet.detect(rawdata)
        encoding = result["encoding"]

        with self.csv.open(newline="", encoding=encoding) as csv_f:
            if csv.Sniffer().has_header(csv_f.read(1024)):
                self.csv_dialect = csv.Sniffer().sniff(csv_f.read(1024))
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=self.csv_dialect)
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
                combo_index = search_keyword(["MATRIK", "REGISTRATION", "STUDENT_ID"])
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

                self.csv_col_selection_revealer.set_reveal_child(True)
            else:
                raise RuntimeError("Unimplemented")

    @Gtk.Template.Callback()
    def combo_changed(self, widget):
        if self.points_combo.get_active() != 0 or self.grade_combo.get_active() != 0:
            self.patch_button.set_sensitive(True)
        else:
            self.patch_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_quote_toggle(self, widget):
        if self.quote_toggle_button.get_active():
            self.csv_dialect.quoting = csv.QUOTE_ALL
        else:
            self.csv_dialect.quoting = csv.QUOTE_NONE

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.response(Gtk.ResponseType.CANCEL)

    @Gtk.Template.Callback()
    def patch_clicked(self, widget):
        self.response(Gtk.ResponseType.OK)
