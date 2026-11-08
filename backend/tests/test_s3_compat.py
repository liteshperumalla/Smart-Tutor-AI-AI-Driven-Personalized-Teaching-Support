"""S3 client factory honours S3_ENDPOINT_URL (Cloudflare R2 and other S3-compatible stores)."""

import pytest

from backend.cloud import aws_helpers
from backend.config import config


@pytest.fixture
def captured(monkeypatch):
    calls = []
    import boto3

    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: calls.append((service, kwargs)) or object())
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(config, "AWS_ACCESS_KEY_ID", "AKIA_AWS")
    monkeypatch.setattr(config, "AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setattr(config, "AWS_SESSION_TOKEN", "aws-token")
    for name in ("S3_ENDPOINT_URL", "S3_REGION", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        monkeypatch.setattr(config, name, "")
    return calls


def test_plain_aws_s3_is_unchanged(captured):
    aws_helpers.get_s3_client()
    service, kwargs = captured[-1]
    assert service == "s3"
    assert "endpoint_url" not in kwargs
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["aws_access_key_id"] == "AKIA_AWS"
    assert kwargs["aws_session_token"] == "aws-token"


def test_r2_endpoint_region_and_keys(captured, monkeypatch):
    monkeypatch.setattr(config, "S3_ENDPOINT_URL", "https://acct.r2.cloudflarestorage.com")
    monkeypatch.setattr(config, "S3_REGION", "auto")
    monkeypatch.setattr(config, "S3_ACCESS_KEY_ID", "r2-key")
    monkeypatch.setattr(config, "S3_SECRET_ACCESS_KEY", "r2-secret")
    aws_helpers.get_s3_client()
    _, kwargs = captured[-1]
    assert kwargs["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
    assert kwargs["region_name"] == "auto"
    assert kwargs["aws_access_key_id"] == "r2-key"
    assert kwargs["aws_secret_access_key"] == "r2-secret"
    # The AWS session token belongs to the AWS keys, not R2's.
    assert "aws_session_token" not in kwargs


def test_get_boto3_client_s3_goes_through_the_same_factory(captured, monkeypatch):
    monkeypatch.setattr(config, "S3_ENDPOINT_URL", "http://minio:9000")
    aws_helpers.get_boto3_client("s3", config="cfg")
    _, kwargs = captured[-1]
    assert kwargs["endpoint_url"] == "http://minio:9000"
    assert kwargs["config"] == "cfg"


def test_other_services_ignore_the_s3_endpoint(captured, monkeypatch):
    monkeypatch.setattr(config, "S3_ENDPOINT_URL", "http://minio:9000")
    aws_helpers.get_boto3_client("secretsmanager")
    service, kwargs = captured[-1]
    assert service == "secretsmanager"
    assert "endpoint_url" not in kwargs


def test_vector_store_uses_the_factory(captured, monkeypatch):
    from backend.s3_vector_store import S3VectorStore

    monkeypatch.setattr(config, "S3_ENDPOINT_URL", "https://acct.r2.cloudflarestorage.com")
    S3VectorStore(bucket_name="docs", index_cache_path="/nonexistent/index.pkl")
    service, kwargs = captured[-1]
    assert service == "s3"
    assert kwargs["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
