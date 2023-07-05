import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from gi.repository import Gtk

from .exam import ExamTask, PointTable
from .grading_table import GradeTable


def create_save_content(
    examname: str,
    examdate: str,
    point_table: PointTable,
    grading: GradeTable,
    tasks: List[ExamTask],
    password: Optional[str] = None,
    salt: Optional[str] = None,
) -> Dict[str, object]:
    save_content: Dict[str, Any] = {
        "General": {"Name": examname, "Date": examdate},
    }
    task_settings = []
    for t in tasks:
        task_settings.append(t.as_dict())

    if password is not None:
        if salt is None:
            salt = base64.b64encode(os.urandom(32)).decode("utf-8")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=480000,
        )
        save_content["General"]["Encryption"] = {"Salt": salt}

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        f = Fernet(key)

        save_content["PointTable"] = f.encrypt(
            json.dumps(point_table.as_dict()).encode()
        ).decode("utf-8")
        save_content["Tasks"] = f.encrypt(json.dumps(task_settings).encode()).decode(
            "utf-8"
        )
        save_content["Grading"] = f.encrypt(
            json.dumps(grading.export()).encode()
        ).decode("utf-8")

    else:
        save_content["PointTable"] = (point_table.as_dict(),)
        save_content["Tasks"] = task_settings
        save_content["Grading"] = grading.export()
    return save_content


def decrypt_exam_json(encrypted: Dict["str", Any], password: str) -> Dict["str", Any]:
    salt = encrypted["General"]["Encryption"]["Salt"]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode(),
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    f = Fernet(key)

    decrypted = {}
    decrypted["General"] = encrypted["General"]
    decrypted["Tasks"] = json.loads(f.decrypt(encrypted["Tasks"]))
    decrypted["Grading"] = json.loads(f.decrypt(encrypted["Grading"]))
    decrypted["PointTable"] = json.loads(f.decrypt(encrypted["PointTable"]))
    return decrypted


def save_exam(
    parent_window,
    examname: str,
    examdate: str,
    point_table: PointTable,
    grading: GradeTable,
    tasks: List[ExamTask],
    lastpath: Optional[str],
):
    file_choose_dialog = Gtk.FileChooserDialog(
        "Save File",
        parent_window,
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
    # all_files_filter = Gtk.FileFilter()
    # all_files_filter.set_name("All Files")
    # all_files_filter.add_pattern("*")
    if lastpath is not None:
        file_choose_dialog.set_current_folder(lastpath)
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
                parent_window,
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
        lastpath = str(filepath.parent)

        pwd_dialog = SavePwdDialog(parent_window)
        response = pwd_dialog.run()

        passwd = None

        if response == Gtk.ResponseType.OK:
            passwd = pwd_dialog.pwd_entry.get_text()
        elif response == Gtk.ResponseType.CANCEL:
            pwd_dialog.destroy()
            file_choose_dialog.destroy()
            return

        pwd_dialog.destroy()
        save_content = create_save_content(
            examname, examdate, point_table, grading, tasks, passwd
        )
        with filepath.open("w") as savefile:
            savefile.write(json.dumps(save_content, indent=4, sort_keys=True))

    else:
        file_choose_dialog.destroy()


@Gtk.Template(resource_path="/exam-grader/Save_Pwd_Dialog.glade")
class SavePwdDialog(Gtk.MessageDialog):
    __gtype_name__ = "save_pwd_dialog"

    pwd_entry = Gtk.Template.Child("pwd_entry")
    save_button = Gtk.Template.Child("save_button")

    def __init__(self, parent):
        super(Gtk.MessageDialog, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)

    @Gtk.Template.Callback()
    def on_save_clicked(self, widget):
        self.response(Gtk.ResponseType.OK)

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.response(Gtk.ResponseType.CANCEL)

    @Gtk.Template.Callback()
    def on_no_encr_clicked(self, widget):
        self.response(Gtk.ResponseType.REJECT)

    @Gtk.Template.Callback()
    def on_pwd_changed(self, widget):
        if self.pwd_entry.get_text() != "":
            self.save_button.set_sensitive(True)
        else:
            self.save_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_show_pwd_pressed(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(True)

    @Gtk.Template.Callback()
    def on_show_pwd_released(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(False)


@Gtk.Template(resource_path="/exam-grader/Decrypt_Dialog.glade")
class DecryptDialog(Gtk.MessageDialog):
    __gtype_name__ = "decrypt_dialog"

    pwd_entry = Gtk.Template.Child("pwd_entry")
    open_button = Gtk.Template.Child("open_button")

    def __init__(self, parent):
        super(Gtk.MessageDialog, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)

        error_label = Gtk.Label(label="Incorrect passwort")
        error_label.set_margin_start(5)
        error_label.set_margin_end(5)
        self.error_popover = Gtk.Popover.new(self.pwd_entry)
        self.error_popover.add(error_label)
        self.error_popover.set_modal(True)
        self.error_popover.show_all()

    @Gtk.Template.Callback()
    def on_open_clicked(self, widget):
        self.response(Gtk.ResponseType.OK)

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.response(Gtk.ResponseType.CANCEL)

    @Gtk.Template.Callback()
    def on_pwd_changed(self, widget):
        self.error_popover.popdown()
        if self.pwd_entry.get_text() != "":
            self.open_button.set_sensitive(True)
        else:
            self.open_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_show_pwd_pressed(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(True)

    @Gtk.Template.Callback()
    def on_show_pwd_released(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(False)

    def highlight_incorrect_pwd(self):
        self.error_popover.popup()
