# ABOUTME: PKG-13 T2 — task.toml [environment] schema lint at generation time.
# ABOUTME: Guards against silent pydantic drop of unknown [environment].* keys.

import pytest

from razorback_plugin_dab.generate.prepare import (
    TaskTomlError,
    _check_task_toml_environment_keys,
)


def test_real_emitted_environment_keys_are_accepted():
    text = (
        'schema_version = "1.2"\n\n'
        '[task]\nname = "x"\n\n'
        "[environment]\n"
        'docker_image = "img"\n'
        'workdir = "/w"\n'
    )
    _check_task_toml_environment_keys(text, task_name="x")


def test_unknown_environment_key_is_rejected():
    text = (
        '[environment]\n'
        'docker_image = "img"\n'
        'docker_compose = "docker-compose.yaml"\n'
    )
    with pytest.raises(TaskTomlError) as excinfo:
        _check_task_toml_environment_keys(text, task_name="x")
    assert "docker_compose" in str(excinfo.value)


def test_missing_environment_section_is_accepted():
    _check_task_toml_environment_keys('schema_version = "1.2"\n', task_name="x")
