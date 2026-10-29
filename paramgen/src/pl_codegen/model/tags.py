"""Tag registry.

A *tag* is a classification attribute attached to every parameter.  Some tags
are mandatory (they always exist in the descriptor and must be filled in the
editor), some are optional and free-form (``Tag1`` .. ``Tag4``).

Every tag owns an independent ``MemoryOffset`` counter.  All tags follow the
same rule: the counter starts at 0 and advances by ``sizeof(value) * array size``
for every parameter that carries the tag.  See ``layout/tag_offset.py``.

The log id is deliberately **not** in here.  It is a plain ``uint16_t`` on the
descriptor and not a classification a parameter carries: it numbers a value in
the log stream and has no area of its own, so nothing about it follows the tag
rule above.  It lives on :class:`~..model.parameter.Parameter` as ``log_id``.

Adding a new tag means:
  1. adding a ``TagSpec`` below,
  2. adding the matching field to ``parameter_descriptor.h`` (same order),
  3. giving it a label the editor shows.
Nothing else in the tool has to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class TagKind(Enum):
    """What kind of value a tag holds."""

    BOOLEAN = "boolean"        #: TRUE / FALSE
    ENUM = "enum"              #: one of the identifiers in the matching drop-down list
    FREE = "free"              #: integer *or* C identifier, not validated further


@dataclass(frozen=True)
class TagSpec:
    """Static description of one tag."""

    tag_id: str                       #: internal id, also used in the XML file
    label: str                        #: what the editor calls this tag
    descriptor_field: str             #: field name inside ``sParameterDescriptor``
    kind: TagKind
    mandatory: bool                   #: must be present for every enabled parameter
    defines_column: Optional[str] = None   #: which *Defines* column lists the legal values
    description: str = ""

    @property
    def is_boolean(self) -> bool:
        return self.kind is TagKind.BOOLEAN


#: All tags, in the order they appear inside ``sParameterDescriptor``.
TAG_REGISTRY: Tuple[TagSpec, ...] = (
    TagSpec("SystemName", "Tag System Name", "TagSystemName", TagKind.ENUM, True,
            defines_column="SYSTEM NAMES",
            description="Owning sub-system of the parameter."),
    TagSpec("ResetProof", "Tag Reset Proof", "TagResetProof", TagKind.BOOLEAN, True,
            description="Parameter value survives a reset (it is stored)."),
    TagSpec("Loggable", "Tag Loggable", "TagLoggable", TagKind.BOOLEAN, True,
            description="Parameter value is written to the log."),
    TagSpec("LogEncryption", "Tag Log Encryption", "TagLogEncryption", TagKind.BOOLEAN, True,
            description="Parameter value is encrypted where it is stored."),
    TagSpec("ParamMode", "Tag ParamMode", "TagParamMode", TagKind.ENUM, True,
            defines_column="PARAM MODES",
            description="Access mode of the parameter."),
    TagSpec("Tag1", "Tag1", "Tag1", TagKind.FREE, False,
            description="Application defined tag."),
    TagSpec("Tag2", "Tag2", "Tag2", TagKind.FREE, False,
            description="Application defined tag."),
    TagSpec("Tag3", "Tag3", "Tag3", TagKind.FREE, False,
            description="Application defined tag."),
    TagSpec("Tag4", "Tag4", "Tag4", TagKind.FREE, False,
            description="Application defined tag."),
)

TAGS_BY_ID: Dict[str, TagSpec] = {spec.tag_id: spec for spec in TAG_REGISTRY}

#: The tag that decides whether ``Parameter.log_id`` means anything at all.
LOGGABLE_TAG = "Loggable"

#: Field name of the log id inside ``sParameterDescriptor``.  It is not a tag,
#: so it carries no "Tag" prefix - that prefix is what marks a field as one.
LOG_ID_FIELD = "LogId"

#: What the editor calls the log id.
LOG_ID_LABEL = "LogID"


def mandatory_tags() -> List[TagSpec]:
    return [spec for spec in TAG_REGISTRY if spec.mandatory]


def optional_tags() -> List[TagSpec]:
    return [spec for spec in TAG_REGISTRY if not spec.mandatory]
