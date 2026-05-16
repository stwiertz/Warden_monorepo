"""Canonical map-label constants shared across tooling.

Single source of truth for the 14-map list (per
``epics-and-stories.md`` ``tooling-LABEL-002``). Relocated here verbatim by
Story 9.11 from the now-retired Tool 2 labeler so the surviving tools
(Tool 6 ``video_timeline_labeler``, Tool 9 ``roi_detection_tester``) have a
durable, GUI-free home — **no tkinter / no PIL** must ever be imported here.
Exact pre-retirement provenance is preserved in git history and the Story 9.11
File List.
"""

MAP_LABELS = [
    "artefact",
    "atlantis",
    "bastion",
    "ceres",
    "coliseum",
    "engine",
    "helios",
    "horizon",
    "lunar_outpost",
    "outlaw",
    "polaris",
    "silva",
    "the_cliff",
    "the_rock",
]

# Display names for buttons (title-cased, spaces preserved)
LABEL_DISPLAY = {
    "horizon": "Horizon",
    "engine": "Engine",
    "outlaw": "Outlaw",
    "ceres": "Ceres",
    "artefact": "Artefact",
    "silva": "Silva",
    "bastion": "Bastion",
    "polaris": "Polaris",
    "coliseum": "Coliseum",
    "the_cliff": "The Cliff",
    "helios": "Helios",
    "atlantis": "Atlantis",
    "the_rock": "The Rock",
    "lunar_outpost": "Lunar Outpost",
}
