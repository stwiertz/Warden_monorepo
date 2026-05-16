"""Default location of the labeled PNG dataset Tool 6 produces.

Relocated by Story 9.11 from the now-retired Tool 7 default-input-dir helper.
The original lived in ``tools/`` and walked one level up
(``dirname(__file__)/".."``) to reach the ``apps/tooling/`` app root. This
module lives one level deeper (``tools/common/``), so the **sole sanctioned
non-verbatim change in Story 9.11** is the extra ``".."`` — the returned
absolute path must still resolve to ``apps/tooling/output/labeled`` exactly as
the original did from ``tools/`` (asserted in
``tests/test_common_labeled_dataset.py``). Exact pre-retirement provenance is
preserved in git history and the Story 9.11 File List.
"""

import os


def default_labeled_dir() -> str:
    """``apps/tooling/output/labeled`` — intentionally identical to
    ``video_timeline_labeler._default_output_dir()`` so the default labeled-data
    input always equals Tool 6's default output. Two levels up from
    ``tools/common/`` (the tooling app root); ``apps/tooling/output/`` is already
    gitignored."""
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        "output",
        "labeled",
    )


# Backwards-name alias matching the retired Tool 7 ``_default_input_dir`` symbol,
# so repointed survivors can keep their existing local alias if useful.
_default_input_dir = default_labeled_dir
