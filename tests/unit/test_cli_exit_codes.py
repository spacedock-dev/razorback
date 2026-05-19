# ABOUTME: Tests that the CLI maps razorback typed errors to documented exit codes.
# ABOUTME: AC-7: unknown top-level key → SpecError → exit code 10.

from typer.testing import CliRunner

from razorback.cli import app


def test_unknown_top_level_key_exits_10(colima_safe_tmp_path):
    bad = colima_safe_tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\nbenchmark:\n  kind: local\nunknown_key: foo\n"
    )
    res = CliRunner(mix_stderr=False).invoke(app, ["run", str(bad)])
    assert res.exit_code == 10, res.stderr or res.stdout


def test_missing_spec_file_exits_2(colima_safe_tmp_path):
    res = CliRunner(mix_stderr=False).invoke(app, ["run", str(colima_safe_tmp_path / "nope.yaml")])
    assert res.exit_code == 2, res.stderr or res.stdout
