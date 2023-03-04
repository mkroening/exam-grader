from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, unique
from typing import Any, Dict, List, Tuple

from gi.repository import Gtk


@dataclass
class ExamTask:
    name: str
    max_points: int
    id: int

    def as_dict(self) -> Dict[str, Any]:
        return {"Name": self.name, "Max_Points": self.max_points, "ID": self.id}


class GradeState(Enum):
    PASS = 0
    FAIL = 1
    OTHER = 2


@unique
class GradeType(IntEnum):
    NOTE = 0
    NICHT_ERSCHIENEN = 1
    PRÜFUNG_ABGEBROCHEN = 2
    TÄUSCHUNG = 3
    BESTANDEN = 4
    NICHT_ZUGELASSEN = 5
    KEINE_BEURTEILUNG = 6

    def longname(self) -> str:
        return GradeType.longnames()[self]

    def shortname(self) -> str:
        return GradeType.shortnames()[self]

    @classmethod
    def from_shortname(cls, name) -> GradeType:
        for i, n in enumerate(cls.shortnames()):
            if name == n:
                return GradeType(i)
        return GradeType.NOTE

    @classmethod
    def longnames(cls) -> List[str]:
        return [
            "Note",
            "Nicht erschienen",
            "Prüfung abgebrochen",
            "Täuschung",
            "Bestanden",
            "Nicht zugelassen",
            "Keine Beurteilung",
        ]

    @classmethod
    def shortnames(cls) -> List[str]:
        return ["", "X", "PA", "U", "B", "NZ", "Q"]

    @classmethod
    def as_liststore(cls) -> Gtk.ListStore:
        liststore = Gtk.ListStore(str, str)
        for i in zip(cls.longnames(), cls.shortnames()):
            liststore.append(i)
        return liststore


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
        self.all_labels = GradeType.shortnames()[1:] + self.labels
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

        self.liststore = GradeType.as_liststore()

    def grade(self, points: float, type: GradeType) -> Tuple[str, GradeState]:
        """
        Returns the grade,  wether it passes the exam, and wether to count the grade for statistics
        """
        if type == GradeType.NOTE:
            for i, l in enumerate(self.labels):
                if points < self.points_min[i]:
                    if i > 1:
                        return (self.labels[i - 1], GradeState.PASS)
                    else:
                        return (self.labels[i - 1], GradeState.FAIL)
            return (self.labels[-1], GradeState.PASS)
        else:
            return (type.shortname(), GradeState.OTHER)

    def as_dict(self) -> Dict[str, float]:
        return {
            "passing": self.passing,
            "step": self.step,
            "max_points": self.points_maximum,
            "min_step": self.min_step,
        }
