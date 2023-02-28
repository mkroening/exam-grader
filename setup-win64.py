import os
import sys

from cx_Freeze import Executable, setup

root_folder = sys.prefix

include_files = []

# Include these assets in th build
assets = ['LICENSE', '3rd Party Licenses.md']
for asset in assets:
    include_files.append((asset, asset))

# Bundle Gtk dlls
missing_dll = ['libgtk-3-0.dll',
               'libgdk-3-0.dll',
               'libcairo-gobject-2.dll',
               'libpoppler-glib-8.dll',
               'libgdk_pixbuf-2.0-0.dll',
               'libjpeg-8.dll',
               'libpango-1.0-0.dll',
               'libpangocairo-1.0-0.dll',
               'libpangoft2-1.0-0.dll',
               'libpangowin32-1.0-0.dll',
               ]

required_dll_search_paths = os.getenv("PATH", os.defpath).split(os.pathsep)

for dll in missing_dll:
    dll_path = None
    for p in required_dll_search_paths:
        p = os.path.join(p, dll)
        if os.path.isfile(p):
            dll_path = p
            break
    assert dll_path is not None, \
        "Unable to locate {} in {}".format(
            dll,
            required_dll_search_paths,
        )
    include_files.append((dll_path, dll))

# pip doesn't recognize that mingw is a 64bit windows and therefore doesn't include the dlls. We do it manually from the pacman package
missing_rename_dll = [("libiconv-2.dll", "lib/pyzbar/libiconv.dll"), ("libzbar-0.dll", "lib/pyzbar/libzbar-64.dll")]

for (sys_dll, package_dll) in missing_rename_dll:
    for p in required_dll_search_paths:
        dll_path = os.path.join(p, sys_dll)
        if os.path.isfile(dll_path):
            include_files.append((dll_path, package_dll))
            break

# somemore stuff that Gtk needs
required_gi_namespaces = [
    "Gtk-3.0",
    "Gdk-3.0",
    "cairo-1.0",
    "Pango-1.0",
    "GObject-2.0",
    "GLib-2.0",
    "Gio-2.0",
    "GdkPixbuf-2.0",
    "GModule-2.0",
    "Atk-1.0",
    "Poppler-0.18",
    "HarfBuzz-0.0",
]

for ns in required_gi_namespaces:
    subpath = "lib/girepository-1.0/{}.typelib".format(ns)
    fullpath = os.path.join(sys.prefix, subpath)
    assert os.path.isfile(fullpath), (
        "Required file {} is missing" .format(
            fullpath,
        ))
    include_files.append((fullpath, subpath))


# The required non-code assets for gtk
gtkLibs = [
    'etc/fonts',
    'etc/gtk-3.0',
    'lib/gdk-pixbuf-2.0',
    'lib/girepository-1.0',
    'share/fontconfig',
    'share/glib-2.0',
    'share/icons/Adwaita',
]

for lib in gtkLibs:
    include_files.append((os.path.join(root_folder, lib), lib))


base = None
# Prevent command line window to open with the GUI
# if sys.platform == "win32":
#    base = "Win32GUI"

buildOptions = dict(
    includes=["gi"],
    excludes=["tkinter"],
    packages=["gi", "cairo"],
    include_files=include_files,
)


setup(name="exam-scan-manager",
      version="0.1",
      description="My GUI application!",
      options=dict(build_exe=buildOptions),
      executables=[Executable("bin/exam_scan_manager", base=base)])
