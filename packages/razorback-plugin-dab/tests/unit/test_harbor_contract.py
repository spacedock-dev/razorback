# ABOUTME: PKG-13 T0 harbor-shape contract check guarding T1/T2.
# ABOUTME: Locks down EnvironmentConfig shape + compose discovery path at the pinned harbor version.

import inspect

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig


def test_environment_config_has_no_docker_compose_field():
    """Harbor's EnvironmentConfig has no docker_compose field.

    The plugin's emitted task.toml must not include
    [environment].docker_compose because pydantic silently drops it.
    """
    assert "docker_compose" not in EnvironmentConfig.model_fields


def test_environment_docker_compose_path_is_environment_dir():
    """Harbor's compose discovery hard-codes environment_dir / docker-compose.yaml.

    The plugin must write its generated compose to
    <task-dir>/environment/docker-compose.yaml for it to be loaded.
    """
    src = inspect.getsource(DockerEnvironment._environment_docker_compose_path.fget)
    assert 'self.environment_dir / "docker-compose.yaml"' in src
