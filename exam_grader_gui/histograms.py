from typing import Callable, Collection, Dict, List, Optional, Union

import matplotlib
from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .exam import PointTable


class Histogram:
    heights: Collection[int]
    labels: List[str]

    def __init__(
        self,
        labels: Collection[str],
        area,
        viewport: bool = False,
        values: Optional[Collection[int]] = None,
        title: Optional[str] = None,
        axis_labels: bool = False,
        with_boxplot: bool = False,
        bar_width: float = 0.5,
        tick_formatter: Optional[Callable[[int, int], str]] = None,
    ):
        self.labels = list(labels)
        self.bar_width = bar_width
        mplfigure = Figure(figsize=(10, 2), dpi=100)

        self.ax = mplfigure.add_subplot(111)
        self.ax.yaxis.set_major_locator(MaxNLocator(integer=True))

        self.bars: List[matplotlib.container.BarContainer] = []
        if values is None:
            self.heights = [0] * len(labels)
            self.update_bars(labels, self.heights)
        else:
            self.heights = list(values)
            assert len(values) == len(labels)
            self.update_bars(labels, values)

        if title is not None:
            self.ax.set_title(title)
        if axis_labels:
            self.ax.set_ylabel("Count")
            self.ax.set_xlabel("Points")

        self.with_boxplot = with_boxplot
        if self.with_boxplot:
            self.box_ax = self.ax.twinx()
            self.box_ax.set_ylim(0, 1)
        self.tick_formatter = tick_formatter

        self.ax.plot()
        self.canvas = FigureCanvas(mplfigure)
        self.canvas.set_size_request(400, 200)
        if viewport:
            area.set_child(self.canvas)
        else:
            area.append(self.canvas)

    def draw(self) -> None:
        if self.with_boxplot:
            points: List[int] = []
            for i, h in enumerate(self.heights):
                points += [i] * h
            self.recreate_boxplot(points)
        self.ax.autoscale_view()
        self.canvas.draw()
        self.canvas.flush_events()

    def update_heights(self, heights: Collection[int]):
        self.heights = heights
        assert len(heights) == len(self.bars)
        for b, h in zip(self.bars, heights):
            b.set_height(h)
        self.ax.relim()
        self.ax.autoscale()
        if self.ax.get_ylim()[1] < 1:
            self.ax.set_ylim(0, 1)

    def update_heights_from_histogram(self, histogram: Dict[str, int]):
        heights = list(map(lambda l: histogram[l], self.labels))
        self.update_heights(heights)

    def update_bars(
        self,
        labels: Collection[Union[str, float, int]],
        heights: Collection[int],
    ):
        for b in self.bars:
            b.remove()
        self.bars = list(
            self.ax.bar(
                labels,
                heights,
                width=self.bar_width,
                color=["tab:red"] + ["tab:blue"] * (len(labels) - 1),
            )
        )
        if self.ax.get_ylim()[1] < 1:
            self.ax.set_ylim(0, 1)
        self.ax.relim()

    def recreate_boxplot(self, points: Collection[float]):
        assert self.with_boxplot
        self.box_ax.clear()
        style = dict(alpha=0.25)
        self.box_ax.boxplot(
            points,
            vert=False,
            positions=[0.8],
            widths=0.1,
            boxprops=style,
            flierprops=style,
            whiskerprops=style,
            capprops=style,
            meanprops=style,
            manage_ticks=False,
        )
        self.box_ax.set_yticks([])
        self.box_ax.set_ylim(bottom=0.0, top=1.0)
        # The box axis overwrites the tick labes. This is a dirty workaround to
        # scale the box_axis labels back to the real ones
        if self.tick_formatter is not None:
            self.box_ax.xaxis.set_major_formatter(self.tick_formatter)
        self.box_ax.xaxis.set_major_locator(MaxNLocator(integer=True))


class GradeHistogram(Histogram):
    def __init__(
        self,
        point_table: PointTable,
        area,
        viewport: bool = False,
        values: Optional[Collection[int]] = None,
    ):
        super().__init__(
            point_table.labels,
            area,
            viewport,
            values,
        )


class PointHistogram(Histogram):
    def __init__(
        self,
        max_points: float,
        area,
        viewport: bool = False,
        values: Optional[Collection[int]] = None,
        bucket_size: float = 0.5,
        title: Optional[str] = None,
        axis_labels: bool = False,
        with_boxplot: bool = False,
    ):
        self.bucket_size = bucket_size
        self.max_points = max_points
        labels = [str(i * bucket_size) for i in range(int(max_points / bucket_size))]
        if values is not None:
            assert len(values) == len(labels)
        super().__init__(
            labels,
            area,
            viewport,
            values,
            title,
            axis_labels,
            with_boxplot,
            bar_width=0.4,
            tick_formatter=self.fmt_ticks,
        )
        self.separators: List[matplotlib.lines.Line2D] = []

    def recolor(self, pass_point: float):
        fail_bar_nr = int(pass_point / self.bucket_size)
        for i, b in enumerate(self.bars):
            if i < fail_bar_nr:
                b.set_color("tab:red")
            else:
                b.set_color("tab:blue")

    def clear_separators(self):
        for s in self.separators:
            s.remove()
        self.separators.clear()

    def update_separators(self, seps: Collection[float]):
        self.clear_separators()
        for s in seps:
            if s != 0.0:
                self.separators.append(
                    self.ax.axvline(
                        s / self.bucket_size - self.bucket_size / 2,
                        alpha=0.1,
                        lw=0.5,
                        c="black",
                    )
                )

    def update_from_histogram(
        self,
        point_histogram: Dict[float, int],
        pass_point: Optional[float] = None,
        separators: Optional[Collection[float]] = None,
    ):
        labels = []
        vals = []
        for k, v in sorted(point_histogram.items()):
            labels.append(k)
            vals.append(v)
        self.update_bars(labels, vals)
        if separators is not None:
            self.update_separators(separators)
        if pass_point is not None:
            self.recolor(pass_point)

    def relimit_x_axis(self, new_max: float):
        if new_max < self.max_points:
            for b in self.bars[int(new_max / self.bucket_size) :]:
                b.remove()
            del self.bars[int(new_max / self.bucket_size) :]
            del self.labels[int(new_max / self.bucket_size) :]
        else:
            new_pos = [
                i + 1 + self.max_points / self.bucket_size
                for i in range(int((new_max - self.max_points) / self.bucket_size))
            ]
            new_labels = [str(i * self.bucket_size) for i in new_pos]
            self.bars += self.ax.bar(
                new_pos,
                [0] * len(new_labels),
                label=new_labels,
                width=self.bar_width,
                color="tab:blue",
            )
            self.labels += new_labels
        self.ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        self.max_points = new_max
        self.ax.autoscale_view()

    def fmt_ticks(self, x, pos) -> str:
        """Scales the value to the bucketsize"""
        return str(x * self.max_points / len(self.labels))


class BigPointHistogram(PointHistogram):
    def __init__(
        self,
        max_points: float,
        area,
        viewport: bool = False,
        values: Optional[Collection[int]] = None,
        bucket_size: float = 0.5,
        axis_labels: bool = False,
    ):
        super().__init__(
            max_points,
            area,
            viewport,
            values,
            bucket_size,
            title="Exam Point Distribution",
            axis_labels=axis_labels,
            with_boxplot=True,
        )
        self.canvas.set_size_request(500, 300)
