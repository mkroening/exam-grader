import matplotlib
from typing import List, Optional, Union
from gi.repository import Gdk, GLib, Gtk
from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from .exam import ExamTask


class TaskPointDistributionPlot:

    def __init__(
        self,
        area,
        viewport: bool = False,
    ):
        violinplt_figure = Figure(figsize=(10, 2), dpi=100)
        self.violinplot = violinplt_figure.add_subplot(111)
        self.violinplot.plot()
        self.canvas = FigureCanvas(violinplt_figure)
        self.canvas.set_size_request(500, 300)

        if viewport:
            area.set_child(self.canvas)
        else:
            area.append(self.canvas)

    def clear(self):
        self.violinplot.clear()

    def draw(self, tasks: List[ExamTask], taskpts: List[List[float]]):
        self.clear()

        tasknames = []
        for i, t in enumerate(tasks):
            tasknames.append(("\n" if i % 2 == 1 else "") + t.name)

        if sum(len(pts) for pts in taskpts) > 0:
            self.violinplot.violinplot(taskpts, showmedians=True)
            self.violinplot.set_xticks(
                [y + 1 for y in range(len(taskpts))], labels=tasknames
            )
            maxpoints = 1
            for i, t in enumerate(tasks):
                self.violinplot.hlines(
                    t.max_points, i + 0.7, i + 1.3, linewidth=2, color="black"
                )
                if t.max_points > maxpoints:
                    maxpoints = t.max_points
            self.violinplot.set_ylim(ymin=0, ymax=maxpoints)
            self.violinplot.set_title("Task Point Distributions")
            self.violinplot.set_ylabel("Points")
            self.violinplot.plot()
        self.canvas.draw()
        self.canvas.flush_events()
