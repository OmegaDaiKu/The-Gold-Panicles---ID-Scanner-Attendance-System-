"""System-wide enumeration constants and official publication designations."""

from enum import Enum
from typing import Dict, List, Optional


class AttendanceCategory(str, Enum):
    """Attendance session classification."""

    DUTY = "Duty"
    VISIT = "Visit"


class SessionStatus(str, Enum):
    """Lifecycle state for staff sessions and visitor records."""

    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    RESOLVED = "RESOLVED"


# ---------------------------------------------------------------------------
# Official Publication Designations
# ---------------------------------------------------------------------------

DESIGNATION_DEPARTMENTS: Dict[str, List[str]] = {
    "Publication Advisers": [
        "Chief Adviser",
        "Technical Adviser for Scribes",
        "Technical Adviser for Visuals",
    ],
    "Executive Board": [
        "Editor-in-Chief",
        "Managing Editor",
        "Technical Editor",
        "Creative Director",
    ],
    "Managerial Department": [
        "Associate Managing Editor",
        "Human Resource Manager",
        "Circulations Manager",
        "Online Accounts Manager",
    ],
    "Creatives Department": [
        "Newsletter Editor",
        "Graphic Design Director",
        "Illustrations Director",
        "Videojournalism Director",
        "Photojournalism Director",
        "Graphic Designer",
        "Illustrator",
        "Videojournalist",
        "Photojournalist",
    ],
    "Scribes Department": [
        "News Editor",
        "Opinion Editor",
        "Sports Editor",
        "Feature Editor",
        "Literary Editor",
        "News Writer",
        "Opinion Writer",
        "Sports Writer",
        "Feature Writer",
        "Literary Writer",
    ],
}

OFFICIAL_DESIGNATIONS: List[str] = [
    designation
    for department_designations in DESIGNATION_DEPARTMENTS.values()
    for designation in department_designations
]

DESIGNATION_SLOT_LIMITS: Dict[str, Optional[int]] = {
    # Publication Advisers
    "Chief Adviser": 1,
    "Technical Adviser for Scribes": 1,
    "Technical Adviser for Visuals": 1,
    # Executive Board
    "Editor-in-Chief": 1,
    "Managing Editor": 1,
    "Technical Editor": 1,
    "Creative Director": 1,
    # Managerial Department
    "Associate Managing Editor": 1,
    "Human Resource Manager": 1,
    "Circulations Manager": 1,
    "Online Accounts Manager": 2,
    # Creatives Department -- director-level
    "Newsletter Editor": 1,
    "Graphic Design Director": 1,
    "Illustrations Director": 1,
    "Videojournalism Director": 1,
    "Photojournalism Director": 1,
    # Creatives Department -- unlimited base-level
    "Graphic Designer": None,
    "Illustrator": None,
    "Videojournalist": None,
    "Photojournalist": None,
    # Scribes Department -- editor-level
    "News Editor": 1,
    "Opinion Editor": 1,
    "Sports Editor": 1,
    "Feature Editor": 1,
    "Literary Editor": 1,
    # Scribes Department -- unlimited base-level
    "News Writer": None,
    "Opinion Writer": None,
    "Sports Writer": None,
    "Feature Writer": None,
    "Literary Writer": None,
}


def get_designation_department(designation: str) -> Optional[str]:
    """Returns the department name a given designation belongs to, or None if unrecognized."""
    for department, designations in DESIGNATION_DEPARTMENTS.items():
        if designation in designations:
            return department
    return None


def get_slot_limit(designation: str) -> Optional[int]:
    """Returns the max concurrent headcount allowed for a designation, or None if unlimited."""
    return DESIGNATION_SLOT_LIMITS.get(designation)


def is_unlimited_designation(designation: str) -> bool:
    """Returns True if the designation has no slot cap (also True for unrecognized strings)."""
    return get_slot_limit(designation) is None