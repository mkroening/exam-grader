from gi.repository import Gtk
from pathlib import Path
import csv


@Gtk.Template(
    filename=str((Path(__file__) / "../glade/Csv_Import_Dialog.glade").resolve())
)
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

    def __init__(self, parent):
        super(Gtk.Dialog, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)

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
                self.stud_id_combo.set_model(model)
                self.stud_id_combo.set_active(0)
                self.first_name_combo.set_model(model)
                self.first_name_combo.set_active(0)
                self.surname_combo.set_model(model)
                self.surname_combo.set_active(0)
                self.trial_nr_combo.set_model(model)
                self.trial_nr_combo.set_active(0)
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
