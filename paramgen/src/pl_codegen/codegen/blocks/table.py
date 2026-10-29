"""ASCII tables, used to draw the parameter list inside a comment block."""

from __future__ import annotations

from typing import List, Sequence


class Table:
    """Produces a bordered ASCII table::

        +---+-----------+-----------+
        | # | Name      | Type      |
        +---+-----------+-----------+
        | 0 | PosDrone  | uint8_t   |
        +---+-----------+-----------+

    The first row is treated as the header.  Every cell is written in full and
    its column grows to fit it: cells used to be cut at 28 characters with a
    '~', so a long parameter name reached the table as 'Position.Home.Latitu~' -
    a name nobody can search for, in the one file meant for looking things up.
    """

    def generate(self, rows: Sequence[Sequence[str]]) -> List[str]:
        """Return the table as a list of lines (no trailing newline)."""
        if not rows:
            return []

        columns = max(len(row) for row in rows)
        table = [[str(cell) for cell in list(row) + [""] * (columns - len(row))]
                 for row in rows]
        widths = [max(len(row[index]) for row in table) for index in range(columns)]

        border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
        lines = [border]
        for index, row in enumerate(table):
            cells = " | ".join(cell.ljust(widths[position])
                               for position, cell in enumerate(row))
            lines.append(f"| {cells} |")
            if index == 0:
                lines.append(border)
        lines.append(border)
        return lines
