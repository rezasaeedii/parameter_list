"""``#include`` directives."""

from __future__ import annotations


class Include:
    """Produces one ``#include`` line.

    ``standard=True``  ->  ``#include <stdint.h>``     (standard library)
    ``standard=False`` ->  ``#include "smart_data.h"`` (project header)
    """

    def __init__(self) -> None:
        pass

    def generate(self, name: str, standard: bool = False) -> str:
        if standard:
            return f"#include <{name}>\n"
        return f'#include "{name}"\n'
