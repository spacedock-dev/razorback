# ABOUTME: PKG-27 AC-3 — DAB-regression structural gate. The harbor + plugin
# ABOUTME: dispatcher path does not call _build_test_sh / _build_environment_compose.

from pathlib import Path


def test_plugin_dispatch_does_not_call_test_sh_synthesis() -> None:
    """AC-3: the generic harbor plugin dispatcher does not reach PKG-27's
    surface (_build_test_sh / _materialize_tests_dir / _build_environment_compose /
    docker-socket bind).
    """
    import razorback.translate as translate_module

    src = Path(translate_module.__file__).read_text()
    body_start = src.index("def _invoke_plugin_generate")
    rest = src[body_start + 1:]
    next_def = rest.find("\ndef ")
    body_end = body_start + 1 + next_def if next_def != -1 else len(src)
    body = src[body_start:body_end]
    assert "_build_test_sh" not in body, (
        "AC-3: plugin dispatcher must not invoke PKG-27's test.sh synthesis"
    )
    assert "_materialize_tests_dir" not in body, (
        "AC-3: plugin dispatcher must not invoke PKG-27's tests-dir materializer"
    )
    assert "_build_environment_compose" not in body, (
        "AC-3: plugin dispatcher must not invoke PKG-27's compose synthesizer"
    )
    assert "docker.sock" not in body, (
        "AC-3: plugin dispatcher must not bind the docker socket"
    )


def test_dab_plugin_prepare_does_not_call_test_sh_synthesis() -> None:
    """AC-3: the plugin materializer does not reach into ade-bench's PKG-27 surface."""
    import razorback_plugin_dab.generate.prepare as prepare_module

    src = Path(prepare_module.__file__).read_text()
    assert "_build_test_sh" not in src
    assert "_materialize_tests_dir" not in src
    assert "_build_environment_compose" not in src
    assert "docker.sock" not in src
