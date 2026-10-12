"""Moves part of a PDF page down without redrawing it.

A PDF page is a list of drawing instructions ("put this text at x, y", "draw
this line"). To open a gap for a new line of text, every instruction that
draws below the gap has its position changed, and nothing else: fonts, sizes,
colours and spacing stay exactly as the original file has them.

Coordinates here are PDF coordinates: the origin is the bottom-left corner and
y grows upwards, so "moving down" means subtracting from y.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pikepdf

# A transform as PDF writes it: [a b c d e f], applied to a row vector.
Matrix = tuple[float, float, float, float, float, float]
Point = tuple[float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_PAINT = frozenset({"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"})
# How many (x, y) pairs each path instruction carries.
_PATH_POINTS = {"m": 1, "l": 1, "c": 3, "v": 2, "y": 2}


class CannotShiftError(Exception):
    """The page is built in a way that cannot be moved safely."""


@dataclass(frozen=True)
class Cut:
    """Everything drawn below `y` moves down by `distance`."""

    y: float
    distance: float


def _multiply(first: Matrix, second: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _apply(point: Point, matrix: Matrix) -> Point:
    x, y = point
    a, b, c, d, e, f = matrix
    return (x * a + y * c + e, x * b + y * d + f)


def _undo_scale(vector: Point, matrix: Matrix) -> Point:
    """The vector that `matrix` (ignoring its offset) turns into `vector`."""
    a, b, c, d, _, _ = matrix
    determinant = a * d - b * c
    if abs(determinant) < 1e-9:
        raise CannotShiftError("The page uses a transform that cannot be reversed.")
    x, y = vector
    return ((x * d - y * c) / determinant, (y * a - x * b) / determinant)


def _number(value: float) -> Decimal:
    return Decimal(f"{value:.4f}").normalize() + Decimal(0)


def _make(operator: str, *operands: Any) -> pikepdf.ContentStreamInstruction:
    cleaned = [_number(op) if isinstance(op, float) else op for op in operands]
    return pikepdf.ContentStreamInstruction(cleaned, pikepdf.Operator(operator))


class _Shifter:
    def __init__(
        self, cuts: Sequence[Cut], images: frozenset[str], forms: dict[str, tuple[Point, Point]]
    ) -> None:
        self.cuts = cuts
        self.images = images
        self.forms = forms
        self.out: list[Any] = []
        self.ctm: Matrix = IDENTITY
        self.leading = 0.0
        self.stack: list[tuple[Matrix, float]] = []
        # Where the current line of text really starts (before any move), and
        # how far the line being written has been moved so far.
        self.line: Matrix = IDENTITY
        self.moved = 0.0
        self.path: list[tuple[int, list[Point]]] = []

    def distance_at(self, y: float) -> float:
        return sum(cut.distance for cut in self.cuts if y < cut.y)

    def _down(self, distance: float) -> Point:
        """A move straight down the page, expressed in the current drawing space."""
        return _undo_scale((0.0, -distance), self.ctm)

    # --- text

    def _start_line(self, tx: float, ty: float) -> Point | None:
        """Moves to a new text line. Returns the corrected offset when it has to change."""
        self.line = _multiply((1.0, 0.0, 0.0, 1.0, tx, ty), self.line)
        y = _apply((self.line[4], self.line[5]), self.ctm)[1]
        wanted = self.distance_at(y)
        if wanted == self.moved:
            return None
        # The previous line was moved by `self.moved`; this one needs `wanted`.
        dx, dy = _undo_scale(self._down(wanted - self.moved), self.line)
        self.moved = wanted
        return (tx + dx, ty + dy)

    def _text(self, operator: str, operands: list[Any], instruction: Any) -> None:
        if operator == "BT":
            self.line, self.moved = IDENTITY, 0.0
            self.out.append(instruction)
        elif operator == "TL":
            self.leading = float(operands[0])
            self.out.append(instruction)
        elif operator == "Tm":
            values = [float(op) for op in operands]
            self.line = (values[0], values[1], values[2], values[3], values[4], values[5])
            y = _apply((values[4], values[5]), self.ctm)[1]
            self.moved = self.distance_at(y)
            dx, dy = self._down(self.moved)
            self.out.append(_make("Tm", *operands[:4], values[4] + dx, values[5] + dy))
        elif operator in ("Td", "TD"):
            tx, ty = float(operands[0]), float(operands[1])
            if operator == "TD":
                self.leading = -ty
            fixed = self._start_line(tx, ty)
            if fixed is None:
                self.out.append(instruction)
                return
            if operator == "TD":
                self.out.append(_make("TL", -ty))
            self.out.append(_make("Td", fixed[0], fixed[1]))
        else:  # T*, ' and " all begin with "go to the next line"
            fixed = self._start_line(0.0, -self.leading)
            if fixed is None:
                self.out.append(instruction)
                return
            if operator == '"':
                self.out.append(_make("Tw", operands[0]))
                self.out.append(_make("Tc", operands[1]))
            self.out.append(_make("Td", fixed[0], fixed[1]))
            if operator != "T*":
                self.out.append(_make("Tj", operands[-1]))

    # --- lines, boxes and pictures

    def _uniform_distance(self, points: list[Point]) -> float:
        """How far a shape moves: only if every part of it is on the same side of every cut."""
        heights = [_apply(point, self.ctm)[1] for point in points]
        top, bottom = self.distance_at(max(heights)), self.distance_at(min(heights))
        return top if top == bottom else 0.0

    def _finish_path(self) -> None:
        points = [point for _, group in self.path for point in group]
        distance = self._uniform_distance(points) if points else 0.0
        if distance:
            dx, dy = self._down(distance)
            for index, _ in self.path:
                old = self.out[index]
                operands = list(old.operands)
                # "re" is x y width height: only its corner moves.
                pairs = 1 if str(old.operator) == "re" else len(operands) // 2
                for pair in range(pairs):
                    operands[pair * 2] = float(operands[pair * 2]) + dx
                    operands[pair * 2 + 1] = float(operands[pair * 2 + 1]) + dy
                self.out[index] = _make(str(old.operator), *operands)
        self.path = []

    def _placed(self, corners: list[Point], instruction: Any, whole: bool) -> None:
        heights = [_apply(corner, self.ctm)[1] for corner in corners]
        top, bottom = self.distance_at(max(heights)), self.distance_at(min(heights))
        if top != bottom:
            if whole:
                raise CannotShiftError("A grouped part of the page sits across the gap.")
            self.out.append(instruction)  # a picture across the gap stays where it is
            return
        if not top:
            self.out.append(instruction)
            return
        dx, dy = self._down(top)
        self.out += [_make("q"), _make("cm", 1, 0, 0, 1, dx, dy), instruction, _make("Q")]

    # --- the walk

    def run(self, instructions: Sequence[Any]) -> list[Any]:
        unit = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
        for instruction in instructions:
            if isinstance(instruction, pikepdf.ContentStreamInlineImage):
                self._placed(unit, instruction, whole=False)
                continue
            operator = str(instruction.operator)
            operands = list(instruction.operands)

            if operator == "q":
                self.stack.append((self.ctm, self.leading))
                self.out.append(instruction)
            elif operator == "Q":
                if self.stack:
                    self.ctm, self.leading = self.stack.pop()
                self.out.append(instruction)
            elif operator == "cm":
                values = [float(op) for op in operands]
                self.ctm = _multiply(
                    (values[0], values[1], values[2], values[3], values[4], values[5]), self.ctm
                )
                self.out.append(instruction)
            elif operator in ("BT", "TL", "Tm", "Td", "TD", "T*", "'", '"'):
                self._text(operator, operands, instruction)
            elif operator in _PATH_POINTS:
                values = [float(op) for op in operands]
                points = [(values[i * 2], values[i * 2 + 1]) for i in range(_PATH_POINTS[operator])]
                self.path.append((len(self.out), points))
                self.out.append(instruction)
            elif operator == "re":
                x, y, width, height = (float(op) for op in operands)
                self.path.append((len(self.out), [(x, y), (x + width, y + height)]))
                self.out.append(instruction)
            elif operator in _PAINT:
                self.out.append(instruction)
                self._finish_path()
            elif operator == "Do":
                name = str(operands[0]).lstrip("/")
                if name in self.images:
                    self._placed(unit, instruction, whole=False)
                elif name in self.forms:
                    low, high = self.forms[name]
                    self._placed([low, high], instruction, whole=True)
                else:
                    self.out.append(instruction)
            else:
                self.out.append(instruction)
        return self.out


def shift_down(
    content: bytes,
    cuts: Sequence[Cut],
    *,
    images: frozenset[str] = frozenset(),
    forms: dict[str, tuple[Point, Point]] | None = None,
) -> bytes:
    """Returns the page's drawing instructions with everything below each cut moved down.

    `images` and `forms` name the pictures and grouped drawings the page uses,
    so they can be moved as a whole.
    """
    holder = pikepdf.new()
    instructions = pikepdf.parse_content_stream(pikepdf.Stream(holder, content))
    shifted = _Shifter(cuts, images, forms or {}).run(instructions)
    return pikepdf.unparse_content_stream(shifted)
