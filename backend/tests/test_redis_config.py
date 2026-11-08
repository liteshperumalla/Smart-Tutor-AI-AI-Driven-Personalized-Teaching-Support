"""Redis connection settings are defined once, with a fixed precedence."""

import ast
from pathlib import Path

import pytest

from backend.config import redis_password, redis_ssl

CONFIG_SOURCE = Path(__file__).resolve().parents[1] / "config.py"


def test_each_redis_setting_is_defined_once_in_config():
    # A second assignment silently overrides the first (class attributes),
    # which is how the Secrets Manager token used to be ignored.
    tree = ast.parse(CONFIG_SOURCE.read_text())
    config_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Config")
    names = [
        target.id
        for node in config_cls.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.startswith("REDIS_")
    ]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert duplicates == []


class TestRedisPassword:
    def test_env_var_wins_over_secrets_manager(self):
        assert redis_password({"REDIS_PASSWORD": "from-env"}, {"redis_auth_token": "from-sm"}) == "from-env"

    def test_secrets_manager_when_env_unset_or_empty(self):
        assert redis_password({}, {"redis_auth_token": "from-sm"}) == "from-sm"
        assert redis_password({"REDIS_PASSWORD": ""}, {"redis_auth_token": "from-sm"}) == "from-sm"

    def test_none_when_neither_is_set(self):
        assert redis_password({}, None) == ""
        assert redis_password({}, {"other": "x"}) == ""


class TestRedisSSL:
    @pytest.mark.parametrize("value,expected", [("true", True), ("TRUE", True), ("false", False), (" False ", False)])
    def test_explicit_env_var_wins(self, value, expected):
        assert redis_ssl({"REDIS_SSL": value}, "x.abc123.use1.cache.amazonaws.com") is expected
        assert redis_ssl({"REDIS_SSL": value}, "smart-tutor-redis") is expected

    def test_default_is_tls_only_for_elasticache(self):
        assert redis_ssl({}, "master.smart-tutor.abc123.use1.cache.amazonaws.com") is True
        # The production Redis container and local dev are plain TCP.
        assert redis_ssl({}, "smart-tutor-redis") is False
        assert redis_ssl({}, "redis") is False
        assert redis_ssl({}, "localhost") is False

    def test_empty_env_var_counts_as_unset(self):
        assert redis_ssl({"REDIS_SSL": ""}, "localhost") is False
        assert redis_ssl({"REDIS_SSL": ""}, "x.cache.amazonaws.com") is True
