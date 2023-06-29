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
    lastpath: Optional[str],
    save_content: Dict[str, object],
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

        create_save_content

        with filepath.open("w") as savefile:
            savefile.write(json.dumps(save_content, indent=4, sort_keys=True))

        # dialog = Gtk.MessageDialog(
        #     parent_window,
        #     Gtk.DialogFlags.MODAL
        #     | Gtk.DialogFlags.DESTROY_WITH_PARENT
        #     | Gtk.DialogFlags.USE_HEADER_BAR,
        #     Gtk.MessageType.INFO,
        #     Gtk.ButtonsType.OK,
        #     "File Saved",
        # )
        # dialog.show_all()
        # dialog.run()
        # dialog.destroy()
    else:
        file_choose_dialog.destroy()
