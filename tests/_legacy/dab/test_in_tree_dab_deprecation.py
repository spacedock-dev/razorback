# ABOUTME: AC-5 — kind: dab (in-tree) is dev-only; emits DeprecationWarning naming harbor_dab.
# ABOUTME: harbor_dab stays as the canonical path the warning recommends.

from __future__ import annotations

import warnings

from razorback._legacy.benchmarks.dab.prepare import prepare_dataset_tasks


def test_in_tree_dab_emits_deprecation_warning(tmp_path) -> None:
    data_root = tmp_path / "data"
    (data_root / "query_bookreview").mkdir(parents=True)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            prepare_dataset_tasks(
                data_root=data_root,
                dataset="bookreview",
                tasks_root=tmp_path / "tr",
            )
        except Exception:
            pass

    dep_warnings = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert dep_warnings, "expected DeprecationWarning from in-tree DAB prepare"
    msg = str(dep_warnings[0].message)
    assert "harbor_dab" in msg
    assert "dab" in msg.lower()
