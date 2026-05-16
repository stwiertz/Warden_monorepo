"""Story 9.11 guard: the relocated labeled-dataset default-dir helper must

resolve to the SAME absolute path the now-retired Tool 7 default-input-dir
helper returned from ``tools/``, despite now living one directory deeper in
``tools/common/`` (the extra ``".."`` depth fix is the only sanctioned
non-verbatim change in Story 9.11).
"""

from __future__ import annotations

import os

from tools.common.labeled_dataset import _default_input_dir, default_labeled_dir


def _apps_tooling_root() -> str:
    # This test file is apps/tooling/tests/test_common_labeled_dataset.py
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_default_labeled_dir_resolves_to_apps_tooling_output_labeled():
    expected = os.path.join(_apps_tooling_root(), "output", "labeled")
    assert os.path.normpath(default_labeled_dir()) == os.path.normpath(expected)


def test_default_labeled_dir_parent_is_apps_tooling_not_tools():
    # Regression guard for the depth bug: a verbatim copy into tools/common/
    # would resolve to apps/tooling/tools/output/labeled (one level too shallow).
    resolved = os.path.normpath(default_labeled_dir())
    parent = os.path.basename(os.path.dirname(os.path.dirname(resolved)))
    assert parent == "tooling"
    assert "tools" not in resolved.split(os.sep)[-3:]


def test_backwards_name_alias_is_the_same_callable():
    assert _default_input_dir is default_labeled_dir
