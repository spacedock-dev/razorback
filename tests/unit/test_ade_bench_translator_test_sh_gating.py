# ABOUTME: PKG-27 AC-3 — DAB-regression structural gate. The harbor-DAB
# ABOUTME: translator path does not call _build_test_sh / _build_environment_compose.

from pathlib import Path


def test_harbor_dab_translator_does_not_call_test_sh_synthesis() -> None:
    """AC-3: DAB's translator path does not reach PKG-27's surface
    (_build_test_sh / _materialize_tests_dir / _build_environment_compose /
    docker-socket bind). Structural source-inspection — same gating shape as
    PKG-23's test_harbor_dab_translator_does_not_invoke_ade_bench_materializer.
    """
    import razorback.translate as translate_module

    src = Path(translate_module.__file__).read_text()
    dab_body_start = src.index("def _build_harbor_dab")
    rest = src[dab_body_start + 1:]
    next_def = rest.find("\ndef ")
    dab_body_end = (
        dab_body_start + 1 + next_def if next_def != -1 else len(src)
    )
    dab_body = src[dab_body_start:dab_body_end]
    assert "_build_test_sh" not in dab_body, (
        "AC-3: DAB translator must not invoke PKG-27's test.sh synthesis"
    )
    assert "_materialize_tests_dir" not in dab_body, (
        "AC-3: DAB translator must not invoke PKG-27's tests-dir materializer"
    )
    assert "_build_environment_compose" not in dab_body, (
        "AC-3: DAB translator must not invoke PKG-27's compose synthesizer"
    )
    assert "docker.sock" not in dab_body, (
        "AC-3: DAB translator must not bind the docker socket"
    )


def test_harbor_dab_plugin_prepare_does_not_call_test_sh_synthesis() -> None:
    """AC-3: the plugin materializer does not reach into ade-bench's PKG-27 surface."""
    import razorback_plugin_dab.generate.prepare as prepare_module

    src = Path(prepare_module.__file__).read_text()
    assert "_build_test_sh" not in src
    assert "_materialize_tests_dir" not in src
    assert "_build_environment_compose" not in src
    assert "docker.sock" not in src
