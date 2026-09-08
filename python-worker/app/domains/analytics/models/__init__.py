from enum import Enum


class ExtensionType(str, Enum):
    """Extension types in the BetterBundle ecosystem"""

    ATLAS = "atlas"
    APOLLO = "apollo"
    MERCURY = "mercury"
