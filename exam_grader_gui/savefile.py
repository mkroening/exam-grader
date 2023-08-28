import base64
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
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


def decrypt_exam(exam: Dict[str, Any], pwd: str) -> Optional[Dict[str, Any]]:
    try:
        decrypted_exam = decrypt_exam_json(exam, password=pwd)
        return decrypted_exam
    except InvalidToken:
        return None


@Gtk.Template(resource_path="/exam-grader/Encrypt_Dialog.ui")
class EncryptDialog(Gtk.Window):
    __gtype_name__ = "encrypt_dialog"

    pwd_entry = Gtk.Template.Child("pwd_entry")
    save_encrypt_button = Gtk.Template.Child("save_encrypt_button")

    def __init__(self, parent, callback: Callable[[str], None], filepath: Path):
        super(Gtk.Window, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)
        self.callback = callback
        self.filepath = filepath

    @Gtk.Template.Callback()
    def on_save_encr_clicked(self, widget):
        if self.pwd_entry.get_text() != "":
            self.destroy()
            self.callback(self.filepath, self.pwd_entry.get_text())

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.destroy()

    @Gtk.Template.Callback()
    def on_no_encr_clicked(self, widget):
        self.destroy()
        self.callback(self.filepath, None)

    @Gtk.Template.Callback()
    def on_pwd_changed(self, widget):
        if self.pwd_entry.get_text() != "":
            self.save_encrypt_button.set_sensitive(True)
        else:
            self.save_encrypt_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_show_pwd_pressed(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(True)

    @Gtk.Template.Callback()
    def on_show_pwd_released(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(False)


@Gtk.Template(resource_path="/exam-grader/Decrypt_Dialog.ui")
class DecryptDialog(Gtk.Window):
    __gtype_name__ = "decrypt_dialog"

    pwd_entry = Gtk.Template.Child("pwd_entry")
    decrypt_button = Gtk.Template.Child("decrypt_button")

    def __init__(
        self,
        parent,
        encrypted_data: Any,
        decrypt_fn: Callable[[Any, str], Optional[Any]],
        success_callback: Callable[[Any], None],
    ):
        super(Gtk.Window, self).__init__()
        self.set_transient_for(parent)
        self.set_modal(parent)

        error_label = Gtk.Label(label="Incorrect passwort")
        error_label.set_margin_start(5)
        error_label.set_margin_end(5)
        self.error_popover = Gtk.Popover.new()
        self.error_popover.set_parent(self.pwd_entry)
        self.error_popover.set_child(error_label)

        self.encrypted_data = encrypted_data
        self.decrypt_fn = decrypt_fn
        self.success_callback = success_callback

    @Gtk.Template.Callback()
    def on_open_clicked(self, widget):
        decrypted = self.decrypt_fn(self.encrypted_data, self.pwd_entry.get_text())
        if decrypted is not None:
            self.destroy()
            self.success_callback(decrypted)
        else:
            self.highlight_incorrect_pwd()

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, widget):
        self.destroy()

    @Gtk.Template.Callback()
    def on_pwd_changed(self, widget):
        self.error_popover.popdown()
        if self.pwd_entry.get_text() != "":
            self.decrypt_button.set_sensitive(True)
        else:
            self.decrypt_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def on_show_pwd_pressed(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(True)

    @Gtk.Template.Callback()
    def on_show_pwd_released(self, widget, icon_type, event):
        self.pwd_entry.set_visibility(False)

    def highlight_incorrect_pwd(self):
        self.error_popover.popup()
