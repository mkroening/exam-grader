import csv
from pathlib import Path
from typing import Optional

from gi.repository import Gtk


@Gtk.Template(resource_path="/exam-grader/Csv_Import_Dialog.glade")
class CsvImportDialog(Gtk.Dialog):
    __gtype_name__ = "csv_import_dialog"

    csv_chooser = Gtk.Template.Child("csv_chooser")
    csv_col_selection_revealer = Gtk.Template.Child("csv_col_selection_revealer")
    stud_id_combo = Gtk.Template.Child("stud_id_combo")
    first_name_combo = Gtk.Template.Child("first_name_combo")
    surname_combo = Gtk.Template.Child("surname_combo")
    trial_nr_combo = Gtk.Template.Child("trial_nr_combo")
    cancel_button = Gtk.Template.Child("cancel_button")
    import_button = Gtk.Template.Child("import_button")

    def __init__(self, parent, lastdir: Optional[str] = None):
        super(Gtk.Dialog, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)
        if lastdir is not None:
            self.csv_chooser.set_current_folder(lastdir)

    @Gtk.Template.Callback()
    def on_file_set(self, widget):
        filename = self.csv_chooser.get_filename()
        self.csv = Path(filename)
        with self.csv.open(newline="") as csv_f:
            if csv.Sniffer().has_header(csv_f.read(1024)):
                self.csv_dialect = csv.Sniffer().sniff(csv_f.read(1024))
                csv_f.seek(0)
                reader = csv.DictReader(csv_f, dialect=self.csv_dialect)
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
    def combo_changed(self, widget):
        selections = set()
        selections.add(self.stud_id_combo.get_active())
        selections.add(self.first_name_combo.get_active())
        selections.add(self.surname_combo.get_active())
        selections.add(self.trial_nr_combo.get_active())
        if len(selections) == 4:
            self.import_button.set_sensitive(True)
        else:
            self.import_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.response(Gtk.ResponseType.CANCEL)

    @Gtk.Template.Callback()
    def import_clicked(self, widget):
        self.response(Gtk.ResponseType.OK)
