"""Health checks follow the configured providers, not AWS unconditionally."""

from backend.config import config
from backend.health import HealthChecker


def test_llm_check_uses_groq_config_without_calling_it(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(config, "LLM_MODEL_ID", "llama-3.3-70b-versatile")
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    result = HealthChecker.check_bedrock()
    assert result["status"] == "healthy"
    assert result["provider"] == "groq"
    assert result["model"] == "llama-3.3-70b-versatile"


def test_llm_check_is_unhealthy_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    monkeypatch.setattr(config, "LLM_MODEL_ID", "")
    result = HealthChecker.check_bedrock()
    assert result["status"] == "unhealthy"
    assert "API key" in result["error"]


def test_secrets_manager_skipped_when_secrets_come_from_env(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "env")
    assert HealthChecker.check_secrets_manager()["status"] == "not_applicable"


def test_object_storage_check_on_local_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "S3_DOCUMENTS_BUCKET", "docs")
    monkeypatch.setattr(config, "OBJECT_STORAGE_PROVIDER", "local")
    monkeypatch.setattr(config, "LOCAL_STORAGE_ROOT", str(tmp_path))
    result = HealthChecker.check_s3()
    assert result["status"] == "healthy"
    assert result["provider"] == "local"

    monkeypatch.setattr(config, "LOCAL_STORAGE_ROOT", str(tmp_path / "missing"))
    assert HealthChecker.check_s3()["status"] == "unhealthy"
