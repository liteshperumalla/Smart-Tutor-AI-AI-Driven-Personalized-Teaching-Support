"""AWS Bedrock LLM Adapter

Provides an abstraction layer for AWS Bedrock LLM inference,
supporting Claude 3.5 Sonnet and other Bedrock models.
"""

import boto3
import json
from typing import Optional, Dict, Any, Generator
from datetime import datetime
from backend.config import config
from backend.logger import get_logger
from botocore.config import Config

logger = get_logger(__name__)


class BedrockLLM:
    """AWS Bedrock LLM wrapper for Claude 3.5 Sonnet and other models"""

    # Pricing per 1K tokens (as of December 2025)
    PRICING = {
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {
            "input": 0.003,   # $3 per 1M tokens
            "output": 0.015   # $15 per 1M tokens
        },
        "meta.llama3-1-70b-instruct-v1:0": {
            "input": 0.00099,  # $0.99 per 1M tokens
            "output": 0.00099  # $0.99 per 1M tokens
        }
    }

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """
        Initialize Bedrock LLM client

        Args:
            model_id: Bedrock model identifier
            region: AWS region
            aws_access_key_id: Optional AWS access key (uses env/config if not provided)
            aws_secret_access_key: Optional AWS secret key
        """
        self.model_id = model_id
        self.region = region

        # Initialize boto3 client
        client_kwargs = {"region_name": region}
        access_key = aws_access_key_id or config.AWS_ACCESS_KEY_ID
        secret_key = aws_secret_access_key or config.AWS_SECRET_ACCESS_KEY
        session_token = aws_session_token or config.AWS_SESSION_TOKEN
        if access_key and secret_key:
            client_kwargs.update({
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            })
            if session_token:
                client_kwargs["aws_session_token"] = session_token

        try:
            # Configure timeouts for the boto3 client
            boto_config = Config(
                connect_timeout=60,  # seconds
                read_timeout=60,     # seconds
                retries={'max_attempts': 2} # Add a retry mechanism
            )
            self.client = boto3.client('bedrock-runtime', config=boto_config, **client_kwargs)
            logger.info(f"✓ Bedrock LLM initialized: {model_id} in {region}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Bedrock client: {e}")
            raise

        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        **kwargs
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
        if "claude" in self.model_id.lower():
            return self._generate_claude(
                prompt, max_tokens, temperature, top_p, system_prompt, **kwargs
            )
        elif "llama" in self.model_id.lower():
            return self._generate_llama(
                prompt, max_tokens, temperature, top_p, **kwargs
            )
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")

    def _generate_claude(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system_prompt: Optional[str],
        **kwargs
    ) -> str:
        """Generate using Claude model"""

        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "messages": messages
        }

        if system_prompt:
            request_body["system"] = system_prompt

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # Extract tokens and calculate cost
            usage = response_body.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            cost = self._calculate_cost(input_tokens, output_tokens)

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

            return response_body['content'][0]['text']

        except Exception as e:
            logger.error(f"[Bedrock] Generation error: {e}", exc_info=True)
            raise

    def _generate_llama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs
    ) -> str:
        """Generate using Llama model"""

        request_body = {
            "prompt": prompt,
            "max_gen_len": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # Debug: Log the actual response structure
            logger.info(f"[Bedrock Llama] Response body keys: {list(response_body.keys())}")
            logger.info(f"[Bedrock Llama] Full response: {response_body}")

            # Llama response format
            generated_text = response_body.get('generation', '')

            # Estimate tokens (Llama doesn't provide usage stats)
            input_tokens = len(prompt.split())
            output_tokens = len(generated_text.split())
            cost = self._calculate_cost(input_tokens, output_tokens)

            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost

            if config.ENABLE_COST_TRACKING:
                self._log_cost(input_tokens, output_tokens, cost, prompt[:100])

            logger.info(f"[Bedrock Llama] ~{input_tokens} in + ~{output_tokens} out, cost: ${cost:.4f} (total: ${self.total_cost:.2f})")

            return generated_text

        except Exception as e:
            logger.error(f"[Bedrock Llama] Generation error: {e}", exc_info=True)
            raise

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Stream response using Bedrock (for real-time display)

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they're generated
        """
        if "claude" not in self.model_id.lower():
            # Fallback to non-streaming for non-Claude models
            yield self.generate(prompt, max_tokens, temperature, **kwargs)
            return

        messages = [{"role": "user", "content": prompt}]

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        try:
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            for event in response['body']:
                chunk = json.loads(event['chunk']['bytes'])

                if chunk['type'] == 'content_block_delta':
                    text = chunk['delta'].get('text', '')
                    if text:
                        yield text

        except Exception as e:
            logger.error(f"[Bedrock] Streaming error: {e}", exc_info=True)
            raise

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for request

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = self.PRICING.get(self.model_id, {"input": 0, "output": 0})

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def _log_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        prompt_preview: str
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
                    "total_cost": self.total_cost
                }
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
                self.total_cost / max(1, self.total_input_tokens + self.total_output_tokens)
            ) * 1000
        }


# Convenience function
def create_bedrock_llm(model_id: Optional[str] = None) -> BedrockLLM:
    """Create Bedrock LLM instance with config defaults"""
    return BedrockLLM(
        model_id=model_id or config.BEDROCK_MODEL_ID,
        region=config.AWS_REGION
    )
