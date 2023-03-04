from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class ExamTask:
    name: str
    max_points: int
    id: int

    def as_dict(self) -> Dict[str, Any]:
        return {"Name": self.name, "Max_Points": self.max_points, "ID": self.id}


class PointTable:
    def __init__(
        self, passing: float, step: float, max_pts: float, min_step: float = 0.5
    ):
        self.passing = passing
        self.step = step
        self.points_maximum = max_pts
        self.min_step = min_step

        self.labels = [
            "5.0",
            "4.0",
            "3.7",
            "3.3",
            "3.0",
            "2.7",
            "2.3",
            "2.0",
            "1.7",
            "1.3",
            "1.0",
        ]
        self.points_min = [0.0]
        pm = passing
        for i in range(len(self.labels) - 1):
            self.points_min.append(pm)
            pm += step

        pm = passing - min_step
        self.points_max = [pm]
        for i in range(len(self.labels) - 2):
            pm += step
            self.points_max.append(pm)
        self.points_max.append(max_pts)

    def grade(self, points: float) -> Tuple[str, bool]:
        """
        Returns the grade, and wether it passes the exam
        """
        for i, l in enumerate(self.labels):
            if points < self.points_min[i]:
                return (self.labels[i - 1], i > 1)
        return (self.labels[-1], True)

    def as_dict(self) -> Dict[str, float]:
        return {
            "passing": self.passing,
            "step": self.step,
            "max_points": self.points_maximum,
            "min_step": self.min_step,
        }
