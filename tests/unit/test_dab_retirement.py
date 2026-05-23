from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_active_code_does_not_import_in_tree_dab_adapter() -> None:
    active_roots = [
        REPO_ROOT / "src" / "razorback",
        REPO_ROOT / "tests",
        REPO_ROOT / "examples",
    ]
    forbidden = [
        "razorback." + "benchmarks.dab",
        "benchmarks" + "/dab",
    ]
    offenders: list[str] = []
    for root in active_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "/_legacy/" in f"/{rel}/" or rel.startswith("tests/_legacy/"):
                continue
            if path.suffix not in {".py", ".md", ".yaml", ".yml", ".toml"}:
                continue
            text = path.read_text(errors="ignore")
            for needle in forbidden:
                if needle in text or needle in rel:
                    offenders.append(f"{rel}: {needle}")
    assert offenders == []


def test_in_tree_dab_adapter_directory_is_not_active() -> None:
    assert not (REPO_ROOT / "src" / "razorback" / "benchmarks" / "dab").exists()
