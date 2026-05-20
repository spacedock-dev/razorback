# ABOUTME: AC-9 hydration check — detect LFS-pointer placeholder files under data_root.
# ABOUTME: Raises DatasetNotHydratedError with the exact stderr message named in the plan.

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml


LFS_POINTER_MARKER = b"version https://git-lfs.github.com/spec/v1"


class DatasetNotHydratedError(RuntimeError):
    """Raised when a referenced data file is still an LFS pointer.

    The string representation matches the exact format named in the
    plan's AC-9 implementation contract (Task 6, Step 3).
    """

    def __init__(self, *, dataset_name: str, pointer_path: Path, data_root: Path) -> None:
        self.dataset_name = dataset_name
        self.pointer_path = pointer_path
        self.data_root = data_root
        message = (
            f"razorback-plugin-dab: dataset {dataset_name} not hydrated, "
            f"found LFS pointer at {pointer_path}.\n"
            f"Hydrate with:\n"
            f"  cd {data_root} && git lfs pull"
        )
        super().__init__(message)


def _is_lfs_pointer(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        head = path.read_bytes()[:200]
    except OSError:
        return False
    return LFS_POINTER_MARKER in head


def _enumerate_data_paths(query_dir: Path, db_config: dict) -> Iterable[Path]:
    """Yield every on-disk path the db_config.yaml refers to.

    Covers `sql_file`, `db_path`, and `dump_folder` keys plus any
    `query_dataset/` subtree.
    """
    clients = (db_config or {}).get("db_clients") or {}
    for _client_name, cfg in clients.items():
        if not isinstance(cfg, dict):
            continue
        for key in ("sql_file", "db_path", "dump_folder"):
            ref = cfg.get(key)
            if not ref:
                continue
            target = query_dir / ref
            if key == "dump_folder" and target.is_dir():
                for child in target.rglob("*"):
                    if child.is_file():
                        yield child
            else:
                yield target


def check_hydrated(*, data_root: Path, dataset_name: str) -> None:
    """Raise DatasetNotHydratedError if any data file is an LFS pointer.

    Reads <data_root>/query_<name>/db_config.yaml, enumerates each on-disk
    reference, and inspects the first 200 bytes for the LFS pointer marker.
    """
    query_dir = Path(data_root) / f"query_{dataset_name}"
    cfg_path = query_dir / "db_config.yaml"
    if not cfg_path.exists():
        raise DatasetNotHydratedError(
            dataset_name=dataset_name,
            pointer_path=cfg_path,
            data_root=Path(data_root),
        )
    db_config = yaml.safe_load(cfg_path.read_text()) or {}
    for target in _enumerate_data_paths(query_dir, db_config):
        if _is_lfs_pointer(target):
            raise DatasetNotHydratedError(
                dataset_name=dataset_name,
                pointer_path=target,
                data_root=Path(data_root),
            )
