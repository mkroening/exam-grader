from enum import Enum
from logging import error
from pathlib import Path

from gi.repository import Gtk

from .gui_helpers import show_about_dialog


class GuiPages(Enum):
    EXAM_SETUP = 1
    GRADING = 2


class MainWindow:
    def __init__(self):
        gladefile = Path(__file__) / "../glade/Main_Window.glade"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(gladefile.resolve()))

        self.window = self.builder.get_object("window")

        self.main_stack = self.builder.get_object("main_stack")
        # self.barcode_generation_box = BarcodeGeneratorBox(self)
        # self.main_stack.add_titled(
        #     self.barcode_generation_box, "barcode_generation", "Barcode Generation"
        # )
        # self.scan_sorter = ScanSorter(self)
        # self.main_stack.add_titled(self.scan_sorter, "scan_sorter", "Scan Sorting")

        self.window.show_all()
        handlers = {
            "onDestroy": Gtk.main_quit,
            "on_open_clicked": self.open,
            "on_about_clicked": self.on_about_clicked,
            "export_clicked": self.export,
            "on_main_stack_visible_child_changed": self.on_main_stack_visible_child_changed,
        }
        self.builder.connect_signals(handlers)

        self.help_menu_popover = self.builder.get_object("help_menu_popover")

        self.export_button = self.builder.get_object("export_button")
        self.open_button = self.builder.get_object("open_button")

        self.set_visible_buttons(GuiPages.EXAM_SETUP)

    def on_main_stack_visible_child_changed(self, stack_widget, variable):
        visible_page = stack_widget.get_visible_child_name()
        if visible_page == "scan_sorter":
            self.set_visible_buttons(GuiPages.GRADING)
        elif visible_page == "barcode_generation":
            self.set_visible_buttons(GuiPages.EXAM_SETUP)
        else:
            error(f"Invalid stack page: {visible_page}")
            raise (RuntimeError(f"Invalid stack page: {visible_page}"))

    def set_visible_buttons(self, page: GuiPages):
        if page == GuiPages.EXAM_SETUP:
            self.export_button.set_visible(False)
            self.open_button.set_visible(False)
        elif page == GuiPages.GRADING:
            self.export_button.set_visible(True)
            self.open_button.set_visible(True)

    def on_about_clicked(self, _widget):
        self.help_menu_popover.popdown()
        show_about_dialog(self.window)

    def open(self, _widget):
        pass

    def export(self, _widget):
        pass