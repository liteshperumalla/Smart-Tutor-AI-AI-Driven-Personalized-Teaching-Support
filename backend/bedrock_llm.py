"""AWS Bedrock LLM Adapter

Provides an abstraction layer for AWS Bedrock LLM inference,
supporting Claude 3.5 Sonnet and other Bedrock models.
"""

import boto3
import json
import time
from typing import Optional, Dict, Any, Generator
from datetime import datetime
from backend.config import config
from backend.model_usage import record_model_used
from backend.logger import get_logger
from botocore.config import Config

logger = get_logger(__name__)


class _LLMCall:
    """Timing and the Langfuse generation for one Bedrock call."""

    __slots__ = ("t0", "generation")

    def __init__(self, t0: float, generation: Any = None):
        self.t0 = t0
        self.generation = generation


class BedrockLLM:
    """AWS Bedrock LLM wrapper for Claude 3.5 Sonnet and other models"""

    # Pricing per 1K tokens (as of December 2025)
    # Includes both direct model IDs and cross-region inference profile IDs (us./eu./ap. prefix)
    PRICING = {
        # Claude 5.5 family
        "anthropic.claude-sonnet-5-5":                    {"input": 0.0030,  "output": 0.0150},
        "us.anthropic.claude-sonnet-5-5":                 {"input": 0.0030,  "output": 0.0150},
        "anthropic.claude-haiku-5-5":                     {"input": 0.0008,  "output": 0.0040},
        "us.anthropic.claude-haiku-5-5":                  {"input": 0.0008,  "output": 0.0040},
        # OpenAI models (GPT 6 Luna)
        "openai.gpt-6-luna":                              {"input": 0.0025,  "output": 0.0100},
        "us.openai.gpt-6-luna":                           {"input": 0.0025,  "output": 0.0100},
        # Legacy Claude / Llama (still supported, moving to retirement in Bedrock)
        "anthropic.claude-3-5-sonnet-20241022-v2:0":      {"input": 0.0030,  "output": 0.0150},
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0":   {"input": 0.0030,  "output": 0.0150},
        "anthropic.claude-3-5-haiku-20241022-v1:0":       {"input": 0.0008,  "output": 0.0040},
        "us.anthropic.claude-3-5-haiku-20241022-v1:0":    {"input": 0.0008,  "output": 0.0040},
        "anthropic.claude-3-haiku-20240307-v1:0":         {"input": 0.00025, "output": 0.00125},
        "us.anthropic.claude-3-haiku-20240307-v1:0":      {"input": 0.00025, "output": 0.00125},
        "meta.llama3-70b-instruct-v1:0":                  {"input": 0.00099, "output": 0.00099},
        "meta.llama3-1-70b-instruct-v1:0":                {"input": 0.00099, "output": 0.00099},
        "us.meta.llama3-1-70b-instruct-v1:0":             {"input": 0.00099, "output": 0.00099},
        # Current-generation Claude 4.x family (Active in Bedrock as of 2025)
        "anthropic.claude-haiku-4-5-20251001-v1:0":       {"input": 0.0010,  "output": 0.0050},
        "us.anthropic.claude-haiku-4-5-20251001-v1:0":    {"input": 0.0010,  "output": 0.0050},
        "anthropic.claude-sonnet-4-5-20250929-v1:0":      {"input": 0.0030,  "output": 0.0150},
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0":   {"input": 0.0030,  "output": 0.0150},
        "anthropic.claude-sonnet-4-6":                    {"input": 0.0030,  "output": 0.0150},
        "us.anthropic.claude-sonnet-4-6":                 {"input": 0.0030,  "output": 0.0150},
        "anthropic.claude-opus-4-7":                      {"input": 0.0150,  "output": 0.0750},
        "us.anthropic.claude-opus-4-7":                   {"input": 0.0150,  "output": 0.0750},
        # Active Llama replacements for the legacy 3.x line
        "meta.llama3-3-70b-instruct-v1:0":                {"input": 0.00072, "output": 0.00072},
        "us.meta.llama3-3-70b-instruct-v1:0":             {"input": 0.00072, "output": 0.00072},
        "meta.llama4-scout-17b-instruct-v1:0":            {"input": 0.00018, "output": 0.00072},
        "us.meta.llama4-scout-17b-instruct-v1:0":         {"input": 0.00018, "output": 0.00072},
    }

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """
        Initialize Bedrock LLM client

        Args:
            model_id: Bedrock model identifier (uses config.BEDROCK_MODEL_ID if not provided)
            region: AWS region
            aws_access_key_id: Optional AWS access key (uses env/config if not provided)
            aws_secret_access_key: Optional AWS secret key
        """
        self.model_id = model_id or config.BEDROCK_MODEL_ID
        self.region = region

        # Initialize boto3 client
        client_kwargs = {"region_name": region}
        access_key = aws_access_key_id or config.AWS_ACCESS_KEY_ID
        secret_key = aws_secret_access_key or config.AWS_SECRET_ACCESS_KEY
        session_token = aws_session_token or config.AWS_SESSION_TOKEN
        if access_key and secret_key:
            client_kwargs.update(
                {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                }
            )
            if session_token:
                client_kwargs["aws_session_token"] = session_token

        try:
            # Configure timeouts for the boto3 client
            boto_config = Config(
                connect_timeout=60,  # seconds
                read_timeout=60,  # seconds
                retries={"max_attempts": 2},  # Add a retry mechanism
            )
            self.client = boto3.client(
                "bedrock-runtime", config=boto_config, **client_kwargs
            )
            logger.info(f"✓ Bedrock LLM initialized: {model_id} in {region}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Bedrock client: {e}")
            raise

        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _guardrail_kwargs(self) -> Dict[str, str]:
        """Extra invoke_model kwargs to apply the configured Bedrock
        Guardrail (jailbreak/prompt-attack detection, content filters, PII
        masking). Returns {} when no guardrail is configured, so callers
        can always do **self._guardrail_kwargs() unconditionally."""
        if not config.BEDROCK_GUARDRAIL_ID:
            return {}
        return {
            "guardrailIdentifier": config.BEDROCK_GUARDRAIL_ID,
            "guardrailVersion": config.BEDROCK_GUARDRAIL_VERSION,
        }

    def _check_guardrail_intervention(self, response_body: Dict[str, Any], prompt: str) -> None:
        """Log (but don't block on) a guardrail intervention. The response
        already contains safe blocked-messaging text in place of the real
        completion -- callers stream/return it like any other response --
        this just gives operational visibility into how often it fires."""
        if response_body.get("amazon-bedrock-guardrailAction") == "INTERVENED":
            logger.warning(
                f"[Bedrock] Guardrail intervened (blocked jailbreak/harmful-content "
                f"attempt) for prompt: {prompt[:100]!r}"
            )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate response using Bedrock model

        Args:
            prompt: User prompt/question
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter
            system_prompt: Optional system prompt
            **kwargs: Additional model parameters

        Returns:
            Generated text response
        """
    def _invoke_generate(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system_prompt: Optional[str],
        **kwargs,
    ) -> str:
        if "claude" in model_id.lower():
            return self._generate_claude(
                prompt, max_tokens, temperature, top_p, system_prompt, model_id=model_id, **kwargs
            )
        elif "llama" in model_id.lower():
            return self._generate_llama(
                prompt, max_tokens, temperature, top_p, model_id=model_id, **kwargs
            )
        elif "openai" in model_id.lower():
            return self._generate_converse(
                prompt, max_tokens, temperature, system_prompt, model_id=model_id
            )
        else:
            raise ValueError(f"Unsupported model: {model_id}")

    # Llama's system persona, applied by both the InvokeModel template and Converse.
    LLAMA_SYSTEM_PROMPT = (
        "You are a helpful, knowledgeable AI tutor. "
        "Always provide clear, structured, and educational responses."
    )

    def _converse_request(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> Dict[str, Any]:
        """Arguments for Bedrock's Converse/ConverseStream, which every model
        here supports and which applies each model's own chat template."""
        if system_prompt is None and "llama" in model_id.lower():
            system_prompt = self.LLAMA_SYSTEM_PROMPT
        inference: Dict[str, Any] = {"maxTokens": max_tokens}
        # GPT-6 models are reasoning models and take a reasoning effort, not a
        # sampling temperature.
        if "openai" not in model_id.lower():
            inference["temperature"] = temperature
        request: Dict[str, Any] = {
            "modelId": model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": inference,
        }
        if system_prompt:
            request["system"] = [{"text": system_prompt}]
        if config.BEDROCK_GUARDRAIL_ID:
            request["guardrailConfig"] = {
                "guardrailIdentifier": config.BEDROCK_GUARDRAIL_ID,
                "guardrailVersion": config.BEDROCK_GUARDRAIL_VERSION,
            }
        return request

    def _generate_converse(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
        model_id: Optional[str] = None,
    ) -> str:
        """Generate with the Converse API (used for OpenAI models on Bedrock)."""
        target_model = model_id or self.model_id
        started = self._begin_call(target_model, prompt)
        try:
            response = self.client.converse(
                **self._converse_request(target_model, prompt, max_tokens, temperature, system_prompt)
            )
        except Exception:
            self._record_usage(target_model, started, status="error")
            raise
        if response.get("stopReason") == "guardrail_intervened":
            self._check_guardrail_intervention({"amazon-bedrock-guardrailAction": "INTERVENED"}, prompt)
        # Reasoning models also return reasoningContent blocks; keep only the answer text.
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(block.get("text", "") for block in blocks)
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        cost = self._calculate_cost(input_tokens, output_tokens, target_model)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        if config.ENABLE_COST_TRACKING:
            self._log_cost(input_tokens, output_tokens, cost, prompt[:100])
        self._record_usage(target_model, started, input_tokens, output_tokens)
        record_model_used(target_model)
        return text

    def _stream_converse(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> Generator[str, None, None]:
        """Stream with ConverseStream (Llama and OpenAI models)."""
        started = self._begin_call(self.model_id, prompt)
        usage: Dict[str, int] = {}
        status = "cancelled"  # stays so only if the client stops reading
        try:
            response = self.client.converse_stream(
                **self._converse_request(self.model_id, prompt, max_tokens, temperature, system_prompt)
            )
            recorded = False
            for event in response["stream"]:
                delta = event.get("contentBlockDelta", {}).get("delta", {})
                text = delta.get("text")  # reasoning deltas carry no "text"
                if text:
                    if not recorded:
                        record_model_used(self.model_id)
                        recorded = True
                    yield text
                stop = event.get("messageStop", {}).get("stopReason")
                if stop == "guardrail_intervened":
                    self._check_guardrail_intervention({"amazon-bedrock-guardrailAction": "INTERVENED"}, prompt)
                # The closing metadata event carries the real token usage.
                usage = event.get("metadata", {}).get("usage", usage)
            status = "success"
        except Exception:
            status = "error"
            raise
        finally:
            # Also runs when the client disconnects mid-stream (GeneratorExit).
            self._record_usage(
                self.model_id,
                started,
                usage.get("inputTokens", 0),
                usage.get("outputTokens", 0),
                status=status,
            )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate response using Bedrock model with automatic fallback.

        Args:
            prompt: User prompt/question
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter
            system_prompt: Optional system prompt
            **kwargs: Additional model parameters

        Returns:
            Generated text response
        """
        try:
            return self._invoke_generate(
                self.model_id, prompt, max_tokens, temperature, top_p, system_prompt, **kwargs
            )
        except Exception as exc:
            # If the model has a 'us.' prefix and failed, try without 'us.'
            if self.model_id.startswith("us."):
                alt_model = self.model_id[3:]
                try:
                    logger.warning(
                        f"[Bedrock] Primary model {self.model_id} failed ({exc}). "
                        f"Retrying with direct foundation model ID: {alt_model}"
                    )
                    return self._invoke_generate(
                        alt_model, prompt, max_tokens, temperature, top_p, system_prompt, **kwargs
                    )
                except Exception as alt_exc:
                    logger.warning(f"[Bedrock] Alt model {alt_model} also failed: {alt_exc}")

            # Fallback to default model (e.g. Llama 70B) if primary failed
            default_model = config.BEDROCK_MODEL_ID
            if self.model_id != default_model:
                try:
                    logger.warning(
                        f"[Bedrock] Model {self.model_id} failed ({exc}). "
                        f"Falling back to default model {default_model}..."
                    )
                    return self._invoke_generate(
                        default_model, prompt, max_tokens, temperature, top_p, system_prompt, **kwargs
                    )
                except Exception as fb_exc:
                    logger.error(
                        f"[Bedrock] Fallback to default model {default_model} failed: {fb_exc}"
                    )
            raise

    def _generate_claude(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system_prompt: Optional[str],
        model_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate using Claude model"""
        target_model = model_id or self.model_id
        messages = [{"role": "user", "content": prompt}]

        # Current Claude models reject requests that set both temperature
        # and top_p, so only temperature is sent.
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            request_body["system"] = system_prompt

        started = self._begin_call(target_model, prompt)
        try:
            response = self.client.invoke_model(
                modelId=target_model,
                body=json.dumps(request_body),
                **self._guardrail_kwargs(),
            )

            response_body = json.loads(response["body"].read())
            self._check_guardrail_intervention(response_body, prompt)

            # Extract tokens and calculate cost (priced for the model that
            # actually answered, which differs from self.model_id on fallback)
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost = self._calculate_cost(input_tokens, output_tokens, target_model)

            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost

            # Log cost tracking
            if config.ENABLE_COST_TRACKING:
                self._log_cost(input_tokens, output_tokens, cost, prompt[:100])

            logger.info(
                f"[Bedrock] {input_tokens} in + {output_tokens} out tokens, "
                f"cost: ${cost:.4f} (total: ${self.total_cost:.2f})"
            )

            self._record_usage(target_model, started, input_tokens, output_tokens)
            record_model_used(target_model)
            return response_body["content"][0]["text"]

        except Exception as e:
            self._record_usage(target_model, started, status="error")
            logger.error(f"[Bedrock] Generation error: {e}", exc_info=True)
            raise

    def _format_llama_prompt(self, prompt: str) -> str:
        """Wrap raw prompt in Llama 3 Instruct chat template."""
        return (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n\n"
            f"{self.LLAMA_SYSTEM_PROMPT}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{prompt}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    def _generate_llama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        model_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate using Llama model"""
        target_model = model_id or self.model_id
        formatted_prompt = self._format_llama_prompt(prompt)

        request_body = {
            "prompt": formatted_prompt,
            "max_gen_len": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        started = self._begin_call(target_model, prompt)
        try:
            response = self.client.invoke_model(
                modelId=target_model,
                body=json.dumps(request_body),
                **self._guardrail_kwargs(),
            )

            response_body = json.loads(response["body"].read())
            self._check_guardrail_intervention(response_body, prompt)

            # Llama response format
            generated_text = response_body.get("generation", "")

            # Bedrock reports Llama token counts; fall back to a word-count
            # estimate only if they are missing.
            input_tokens = response_body.get("prompt_token_count") or len(prompt.split())
            output_tokens = response_body.get("generation_token_count") or len(generated_text.split())
            cost = self._calculate_cost(input_tokens, output_tokens, target_model)

            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost

            if config.ENABLE_COST_TRACKING:
                self._log_cost(input_tokens, output_tokens, cost, prompt[:100])

            logger.info(
                f"[Bedrock Llama] ~{input_tokens} in + ~{output_tokens} out, cost: ${cost:.4f} (total: ${self.total_cost:.2f})"
            )

            self._record_usage(target_model, started, input_tokens, output_tokens)
            record_model_used(target_model)
            return generated_text

        except Exception as e:
            self._record_usage(target_model, started, status="error")
            logger.error(f"[Bedrock Llama] Generation error: {e}", exc_info=True)
            raise

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream response using Bedrock (for real-time display)

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt -- kept on Anthropic's
                dedicated system channel rather than folded into the user
                message, so persona/instructions carry Claude's strongest
                instruction-hierarchy signal against prompt injection.

        Yields:
            Text chunks as they're generated
        """
        if "claude" not in self.model_id.lower():
            # Llama and OpenAI models stream through ConverseStream. If it fails
            # before any text arrives, generate() runs its fallback chain.
            yielded = False
            try:
                for text in self._stream_converse(prompt, max_tokens, temperature, system_prompt):
                    yielded = True
                    yield text
                return
            except Exception as e:
                if yielded:
                    raise
                logger.warning(f"[Bedrock] ConverseStream error ({e}); falling back to generate()...")
            yield self.generate(
                prompt, max_tokens, temperature, system_prompt=system_prompt, **kwargs
            )
            return

        messages = [{"role": "user", "content": prompt}]

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            request_body["system"] = system_prompt

        started = self._begin_call(self.model_id, prompt)
        tokens = {"in": 0, "out": 0}
        stream_status = "cancelled"  # stays so only if the client stops reading
        try:
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(request_body),
                **self._guardrail_kwargs(),
            )

            intervened = False
            recorded = False
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])

                if not intervened and chunk.get("amazon-bedrock-guardrailAction") == "INTERVENED":
                    intervened = True
                    self._check_guardrail_intervention(chunk, prompt)

                # Token usage: message_start carries input tokens,
                # message_delta the running output count, and Bedrock's
                # closing invocation metrics carry both.
                if chunk.get("type") == "message_start":
                    tokens["in"] = chunk.get("message", {}).get("usage", {}).get("input_tokens", tokens["in"])
                elif chunk.get("type") == "message_delta":
                    tokens["out"] = chunk.get("usage", {}).get("output_tokens", tokens["out"])
                metrics = chunk.get("amazon-bedrock-invocationMetrics")
                if metrics:
                    tokens["in"] = metrics.get("inputTokenCount", tokens["in"])
                    tokens["out"] = metrics.get("outputTokenCount", tokens["out"])

                if chunk["type"] == "content_block_delta":
                    text = chunk["delta"].get("text", "")
                    if text:
                        if not recorded:
                            record_model_used(self.model_id)
                            recorded = True
                        yield text
            stream_status = "success"

        except Exception as e:
            self._record_usage(self.model_id, started, tokens["in"], tokens["out"], status="error")
            started = None  # recorded; the finally below must not count it twice
            logger.warning(f"[Bedrock] Streaming error ({e}); falling back to generate()...")
            try:
                yield self.generate(
                    prompt, max_tokens, temperature, system_prompt=system_prompt, **kwargs
                )
            except Exception as fb_err:
                logger.error(f"[Bedrock] Streaming fallback also failed: {fb_err}", exc_info=True)
                raise e
        finally:
            # Completed streams and client disconnects (GeneratorExit) land here.
            if started is not None:
                self._record_usage(self.model_id, started, tokens["in"], tokens["out"], status=stream_status)

    def _begin_call(self, model_id: str, prompt: str) -> _LLMCall:
        """Start timing a call and open its Langfuse generation.

        The LlamaIndex callback's generations carry no model or usage, so
        this generation is what Langfuse cost, token and model charts read.
        """
        generation = None
        try:
            from backend.langfuse_setup import get_langfuse_client, request_trace_scope

            client = get_langfuse_client()
            if client is not None:
                # Tag the generation with the requesting user (pseudonym),
                # chat session and feature so Langfuse can group it.
                with request_trace_scope():
                    generation = client.start_observation(
                        name="bedrock-generation",
                        as_type="generation",
                        model=model_id,
                        input=prompt[:4000] if isinstance(prompt, str) else None,
                    )
        except Exception as e:  # tracing must never break generation
            logger.debug(f"[Bedrock] Langfuse generation skipped: {e}")
        return _LLMCall(time.monotonic(), generation)

    def _record_usage(
        self,
        model_id: str,
        started: _LLMCall,
        input_tokens: int = 0,
        output_tokens: int = 0,
        status: str = "success",
    ) -> None:
        """Send one call's latency, tokens and cost to Prometheus and Langfuse."""
        cost = self._calculate_cost(input_tokens, output_tokens, model_id)
        try:
            from backend.metrics import record_llm_usage

            record_llm_usage(
                model=model_id,
                latency_seconds=time.monotonic() - started.t0,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                status=status,
            )
        except Exception as e:  # metrics must never break generation
            logger.debug(f"[Bedrock] usage metrics skipped: {e}")
        if started.generation is not None:
            try:
                started.generation.update(
                    usage_details={"input": input_tokens, "output": output_tokens},
                    cost_details={"total": cost},
                    level="ERROR" if status == "error" else "DEFAULT",
                    status_message=None if status == "success" else status,
                )
                started.generation.end()
            except Exception as e:
                logger.debug(f"[Bedrock] Langfuse generation update skipped: {e}")
            started.generation = None

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model_id: Optional[str] = None) -> float:
        """
        Calculate cost for request

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = self.PRICING.get(model_id or self.model_id, {"input": 0, "output": 0})

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def _log_cost(
        self, input_tokens: int, output_tokens: int, cost: float, prompt_preview: str
    ):
        """Log cost tracking to S3 and local backup"""
        try:
            from backend.cost_tracking import get_cost_tracker

            tracker = get_cost_tracker()
            tracker.log_cost(
                service="bedrock_llm",
                operation="generate",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                model_id=self.model_id,
                metadata={
                    "prompt_preview": prompt_preview,
                    "total_cost": self.total_cost,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to log cost: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "model": self.model_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost,
            "avg_cost_per_request": (
                self.total_cost
                / max(1, self.total_input_tokens + self.total_output_tokens)
            )
            * 1000,
        }


# Convenience function
def create_bedrock_llm(model_id: Optional[str] = None) -> BedrockLLM:
    """Create Bedrock LLM instance with config defaults"""
    return BedrockLLM(
        model_id=model_id or config.BEDROCK_MODEL_ID, region=config.AWS_REGION
    )
