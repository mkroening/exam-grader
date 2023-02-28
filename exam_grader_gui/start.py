#!/usr/bin/env python

from exam_grader_gui import MainWindow
from gi.repository import Gtk


def start():
    MainWindow()

    Gtk.main()

    exit(0)
