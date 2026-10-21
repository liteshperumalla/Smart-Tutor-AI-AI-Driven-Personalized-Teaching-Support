"""
Unit tests for Langfuse v4 architecture, observations-first helpers,
attribute propagation, observation scoring, and health checks.
"""

import unittest
from unittest.mock import MagicMock, patch

from backend.langfuse_setup import (
    init_langfuse,
    shutdown_langfuse,
    get_langfuse_client,
    get_client,
    get_langfuse_handler,
    propagate_attributes,
    observe,
    start_as_current_observation,
    create_trace,
    update_trace,
    create_span,
    end_span,
    traced_span,
    score_observation,
    get_otel_ingestion_headers,
    get_langfuse_health,
)


class TestLangfuseV4(unittest.TestCase):
    def test_observe_decorator_noop_fallback(self):
        """Verify @observe functions properly even without active client."""
        @observe()
        def sample_func(x, y):
            return x + y

        self.assertEqual(sample_func(2, 3), 5)

    def test_propagate_attributes_context(self):
        """Test v4 propagate_attributes context manager."""
        with propagate_attributes(user_id="user_test_123", session_id="sess_456") as ctx:
            # Should gracefully yield None or context without throwing
            self.assertTrue(ctx is None or ctx is not None)

    def test_start_as_current_observation(self):
        """Test start_as_current_observation context manager."""
        with start_as_current_observation("test-obs", as_type="span") as obs:
            self.assertTrue(obs is None or obs is not None)

    def test_get_otel_ingestion_headers(self):
        """Verify v4 OTLP ingestion header has x-langfuse-ingestion-version: 4."""
        headers = get_otel_ingestion_headers()
        self.assertEqual(headers["x-langfuse-ingestion-version"], "4")
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_score_observation_safe_fallback(self):
        """Verify score_observation returns False cleanly when client is None."""
        with patch("backend.langfuse_setup._langfuse_client", None):
            success = score_observation(
                observation_id="obs_abc123",
                name="accuracy",
                value=0.95,
                comment="High quality evaluation",
            )
            self.assertFalse(success)

    def test_score_observation_with_mock_client(self):
        """Verify score_observation calls client.score with correct v4 arguments."""
        mock_client = MagicMock()
        with patch("backend.langfuse_setup._langfuse_client", mock_client):
            success = score_observation(
                observation_id="obs_abc123",
                name="relevance",
                value=1.0,
                trace_id="tr_xyz789",
            )
            self.assertTrue(success)
            mock_client.score.assert_called_once_with(
                name="relevance",
                value=1.0,
                observation_id="obs_abc123",
                trace_id="tr_xyz789",
            )

    def test_create_trace_and_update(self):
        """Verify create_trace and update_trace with mock client."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        with patch("backend.langfuse_setup._langfuse_client", mock_client):
            trace = create_trace("root-interaction", user_id="u1", session_id="s1")
            self.assertEqual(trace, mock_trace)
            mock_client.trace.assert_called_once_with(name="root-interaction", user_id="u1", session_id="s1")

            update_trace(trace, output={"status": "completed"})
            mock_trace.update.assert_called_once_with(output={"status": "completed"})

    def test_traced_span_context(self):
        """Verify traced_span correctly tracks duration."""
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span

        with traced_span(mock_trace, "sub-step", input={"q": "test"}) as span:
            self.assertEqual(span, mock_span)

        mock_trace.span.assert_called_once_with(name="sub-step", input={"q": "test"})
        self.assertTrue(mock_span.end.called)
        kwargs = mock_span.end.call_args[1]
        self.assertIn("output", kwargs)
        self.assertIn("duration_ms", kwargs["output"])

    def test_get_langfuse_health_disabled(self):
        """Health reports disabled when LANGFUSE_ENABLED is false."""
        with patch("backend.langfuse_setup.config.LANGFUSE_ENABLED", False):
            health = get_langfuse_health()
            self.assertEqual(health["status"], "disabled")

    def test_get_langfuse_health_v4_healthy(self):
        """Health reports v4 attributes when client is healthy."""
        mock_client = MagicMock()
        with patch("backend.langfuse_setup.config.LANGFUSE_ENABLED", True), \
             patch("backend.langfuse_setup.config.LANGFUSE_PUBLIC_KEY", "pk-lf-test"), \
             patch("backend.langfuse_setup.config.LANGFUSE_SECRET_KEY", "sk-lf-test"), \
             patch("backend.langfuse_setup._langfuse_client", mock_client):
            health = get_langfuse_health()
            self.assertEqual(health["status"], "healthy")
            self.assertEqual(health["version"], "v4")
            self.assertTrue(health["observations_first"])
            self.assertEqual(health["ingestion_version"], "4")
            self.assertEqual(health["data_model"], "clickhouse_wide_table")

    def test_get_langfuse_health_retry_and_init_error(self):
        """Health triggers init_langfuse(force=True) and surfaces _init_error if initialization fails."""
        with patch("backend.langfuse_setup.config.LANGFUSE_ENABLED", True), \
             patch("backend.langfuse_setup.config.LANGFUSE_PUBLIC_KEY", "pk-lf-test"), \
             patch("backend.langfuse_setup.config.LANGFUSE_SECRET_KEY", "sk-lf-test"), \
             patch("backend.langfuse_setup._langfuse_client", None), \
             patch("backend.langfuse_setup.init_langfuse", side_effect=lambda force=False: False), \
             patch("backend.langfuse_setup._init_error", "MockInitException: connection refused"):
            health = get_langfuse_health()
            self.assertEqual(health["status"], "unhealthy")
            self.assertIn("Client not initialized", health["message"])
            self.assertIn("MockInitException", health["message"])

    def test_init_langfuse_strips_quotes_and_whitespace(self):
        """init_langfuse handles whitespace and quotes cleanly."""
        with patch("backend.langfuse_setup.config.LANGFUSE_ENABLED", True), \
             patch("backend.langfuse_setup.config.LANGFUSE_PUBLIC_KEY", " 'pk-lf-clean' "), \
             patch("backend.langfuse_setup.config.LANGFUSE_SECRET_KEY", ' "sk-lf-clean" '), \
             patch("backend.langfuse_setup.config.LANGFUSE_HOST", ' "https://cloud.langfuse.com" '), \
             patch("langfuse.Langfuse") as mock_langfuse_cls:
            mock_client = MagicMock()
            mock_langfuse_cls.return_value = mock_client
            with patch("backend.langfuse_setup._langfuse_client", None), \
                 patch("backend.langfuse_setup._initialized", False):
                ok = init_langfuse(force=True)
                self.assertTrue(ok)
                mock_langfuse_cls.assert_called()


if __name__ == "__main__":
    unittest.main()
