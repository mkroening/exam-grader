# Exam Grader

This is a tool for grading exams. You can use it to enter the points of the exam participants, modify the grade limits and export the results as CSV for upload to campus management systems (e.g. Moodle).

## Setup

### Python on Linux

Optional: Use a _python venv_:

```bash
sudo apt install python3-venv  # if not installed already
python -m venv .env
source .env/bin/activate
```

#### Install all dependencies:

- Ubuntu:

```bash
sudo apt install python3-pip libgirepository2.0-dev cmake libcairo2-dev python3-chardet python3-matplotlib python3-gi
```

- Fedora:

```bash
sudo dnf install cairo-gobject-devel cmake cairo-devel python3-chardet python3-matplotlib python3-matplotlib-gtk4
```

#### Installation

```bash
# In the projects root folder:
# Prepare the .gresource file
glib-compile-resources --target=ui.gresource resources.xml
# Install Exam Grader
pip install -e .
```

#### Execution

Run it:
```bash
exam-grader
```

## Gallery

![Setup](resources/screenshots/Setup.png)
![Grading](resources/screenshots/Grading.png)
![Graphs](resources/screenshots/Graphs.png)


## License

This tool is licensed under the [GPLv3](LICENSE).
Libraries contained in the Windows package are unmodified and are licensed under their respective license.
