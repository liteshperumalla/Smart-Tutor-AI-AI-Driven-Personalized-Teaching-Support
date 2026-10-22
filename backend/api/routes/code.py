"""Code sandbox API routes for code execution and LLM assistance.

This module provides endpoints for:
- Running student code in the isolated code-runner service (sandbox/code-runner)
- Code generation using AWS Bedrock
- Code explanation and debugging
- Code-related chat assistance
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
import os

from ..dependencies import get_current_user, get_rate_limiter_dep
from backend.rate_limiter import limiter, PerUserRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code", tags=["code"])


def _clean_repeated_content(text: str) -> str:
    """Remove repeated content from LLM responses."""
    if not text:
        return text

    lines = text.split("\n")
    unique_lines = []
    seen = set()

    for line in lines:
        line_stripped = line.strip()
        if line_stripped and line_stripped not in seen:
            unique_lines.append(line)
            seen.add(line_stripped)
        elif not line_stripped:
            unique_lines.append(line)

    cleaned = "\n".join(unique_lines)

    markdown_pattern = r"(```[\s\S]*?```)"
    matches = list(re.finditer(markdown_pattern, cleaned))
    if len(matches) > 1:
        cleaned = matches[0].group(1)

    return cleaned


def _extract_code(text: str) -> str:
    """Extract clean code from LLM response, removing markdown fences and explanations."""
    if not text:
        return text

    code = text.strip()

    code_block_pattern = r"```(\w*)\n([\s\S]*?)```"
    matches = list(re.finditer(code_block_pattern, code))

    if matches:
        first_block = matches[0]
        lang = first_block.group(1)
        extracted_code = first_block.group(2).strip()
        return extracted_code

    return code


SUPPORTED_LANGUAGES = ["python", "javascript", "java", "typescript", "cpp", "go"]


class CodeExecuteRequest(BaseModel):
    """Request to execute code."""

    code: str = Field(..., min_length=1, description="Code to execute")
    language: Literal["python", "javascript", "java", "typescript", "cpp", "go"] = (
        Field(default="python", description="Programming language")
    )


class CodeGenerateRequest(BaseModel):
    """Request to generate code from a prompt."""

    prompt: str = Field(
        ..., min_length=3, description="Description of what to generate"
    )
    language: Literal["python", "javascript", "java", "typescript", "cpp", "go"] = (
        Field(default="python", description="Target programming language")
    )


class CodeExplainRequest(BaseModel):
    """Request to explain code."""

    code: str = Field(..., min_length=1, description="Code to explain")
    language: Literal["python", "javascript", "java", "typescript", "cpp", "go"] = (
        Field(default="python", description="Programming language")
    )


class CodeDebugRequest(BaseModel):
    """Request to debug code."""

    code: str = Field(..., min_length=1, description="Code to debug")
    language: Literal["python", "javascript", "java", "typescript", "cpp", "go"] = (
        Field(default="python", description="Programming language")
    )


class CodeChatRequest(BaseModel):
    """Request for code-related chat."""

    message: str = Field(..., min_length=1, description="Chat message")
    history: Optional[List[dict]] = Field(
        default=None, description="Previous chat history"
    )


class CodeExecuteResponse(BaseModel):
    """Response from code execution."""

    output: str
    success: bool
    error: Optional[str] = None


class CodeGenerateResponse(BaseModel):
    """Response from code generation."""

    code: str
    language: str


class CodeExplainResponse(BaseModel):
    """Response from code explanation."""

    explanation: str


class CodeDebugResponse(BaseModel):
    """Response from code debugging."""

    analysis: str
    fixed_code: Optional[str] = None


class CodeChatResponse(BaseModel):
    """Response from code chat."""

    response: str


def _code_llm_model_id() -> str:
    """Resolve the code LLM model id, overridable via CODE_LLM_MODEL_ID."""
    return os.environ.get(
        "CODE_LLM_MODEL_ID",
        "us.anthropic.claude-5-5-sonnet-20261022-v1:0",
    )


def _get_code_llm():
    """Get the code LLM instance using AWS Bedrock.

    Uses Claude 5.5 Sonnet by default — elite coding model on Bedrock.
    Falls back gracefully to default Bedrock model (Llama) if unavailable.
    """
    try:
        from backend.bedrock_llm import BedrockLLM
        from backend.config import config

        return BedrockLLM(model_id=_code_llm_model_id(), region=config.AWS_REGION)
    except Exception:
        logger.exception("Failed to initialize Bedrock LLM with code model, attempting default model")
        try:
            from backend.bedrock_llm import BedrockLLM
            from backend.config import config

            return BedrockLLM(model_id=config.BEDROCK_MODEL_ID, region=config.AWS_REGION)
        except Exception:
            logger.exception("Unexpected error initializing fallback Bedrock LLM")
            return None


# Student code never runs in this process. It is forwarded to the isolated
# code-runner container (sandbox/code-runner), which has no secrets, no
# internet, a read-only filesystem and per-run CPU/memory/time limits.
RUNNABLE_LANGUAGES = {"python", "javascript", "java"}


def _format_runner_result(result: dict) -> tuple[str, bool]:
    """Turn the runner's JSON into the (output, success) shown in the UI."""
    stdout = result.get("stdout") or ""
    stderr = result.get("stderr") or ""
    exit_code = result.get("exit_code")
    parts = [stdout.rstrip("\n")] if stdout else []
    if stderr:
        label = "Compilation Error" if result.get("stage") == "compile" else "Error"
        parts.append(f"{label}:\n{stderr.rstrip()}")
    if result.get("timed_out"):
        parts.append("⏱ Stopped: the program ran longer than the 10-second limit.")
    elif exit_code is not None and exit_code < 0:
        parts.append("⛔ Stopped: the program hit the sandbox's CPU, memory or output limit.")
    if result.get("truncated"):
        parts.append("✂ Output truncated at 64 KB.")
    success = exit_code == 0 and not result.get("timed_out")
    output = "\n\n".join(p for p in parts if p) or "(no output)"
    return output, success


def _run_in_sandbox(code: str, language: str) -> tuple[str, bool]:
    """POST the code to the code-runner service and format its result."""
    import requests
    from backend.config import config as _cfg

    response = requests.post(
        f"{_cfg.CODE_RUNNER_URL.rstrip('/')}/run",
        json={"language": language, "code": code},
        timeout=_cfg.CODE_RUNNER_TIMEOUT_SECONDS,
    )
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="The code sandbox is busy. Try again in a few seconds.")
    if response.status_code == 413:
        raise HTTPException(status_code=413, detail="That program is too large to run (64 KB limit).")
    response.raise_for_status()
    return _format_runner_result(response.json())


@router.post("/execute", response_model=CodeExecuteResponse)
@limiter.limit("60/hour")
async def execute_code(
    request: Request,
    payload: CodeExecuteRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Run code in the isolated sandbox. Available to any signed-in user."""
    import asyncio
    import requests
    from backend.config import config as _cfg

    if not _cfg.ENABLE_CODE_EXECUTION or not _cfg.CODE_RUNNER_URL:
        raise HTTPException(
            status_code=503,
            detail="Running code isn't available on this server right now. You can still generate, explain and debug code.",
        )
    if payload.language not in RUNNABLE_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Running {payload.language} isn't supported yet. Supported: Python, JavaScript, Java.",
        )
    await rate_limiter.check_rate_limit(request, limit=60, window=3600, scope="code_execute")
    try:
        output, success = await asyncio.to_thread(_run_in_sandbox, payload.code, payload.language)
    except HTTPException:
        raise
    except requests.RequestException:
        logger.exception("Code runner request failed")
        raise HTTPException(status_code=503, detail="The code sandbox is unavailable. Please try again shortly.")
    return CodeExecuteResponse(output=output, success=success, error=None if success else output)


@router.post("/generate", response_model=CodeGenerateResponse)
@limiter.limit("40/hour")
async def generate_code(
    request: Request,
    payload: CodeGenerateRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Generate code from a natural language prompt."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="code_generate")
    await rate_limiter.check_model_rate_limit(request, _code_llm_model_id())
    await rate_limiter.check_cost_budget(request, _code_llm_model_id())
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are a helpful coding assistant. Write ONLY {payload.language} code for the following request. "
        "Output ONLY the code in a single code block. "
        "Do NOT include explanations, comments, or any text before or after the code block."
    )

    try:
        response = llm.generate(
            prompt=f"Request: {payload.prompt}\n\nCode:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        code = _extract_code(response.strip())
        return CodeGenerateResponse(code=code, language=payload.language)
    except Exception as e:
        logger.exception("Code generation failed: %s", e)
        # Attempt fallback to default Bedrock model
        try:
            from backend.bedrock_llm import BedrockLLM
            from backend.config import config
            if llm.model_id != config.BEDROCK_MODEL_ID:
                fallback_llm = BedrockLLM(model_id=config.BEDROCK_MODEL_ID, region=config.AWS_REGION)
                response = fallback_llm.generate(
                    prompt=f"Request: {payload.prompt}\n\nCode:",
                    system_prompt=system_prompt,
                    max_tokens=2048,
                    temperature=0.3,
                )
                code = _extract_code(response.strip())
                return CodeGenerateResponse(code=code, language=payload.language)
        except Exception as fb_err:
            logger.exception("Fallback code generation also failed: %s", fb_err)
        raise HTTPException(status_code=500, detail="Code generation failed")


@router.post("/explain", response_model=CodeExplainResponse)
@limiter.limit("40/hour")
async def explain_code(
    request: Request,
    payload: CodeExplainRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Explain what the code does."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="code_explain")
    await rate_limiter.check_model_rate_limit(request, _code_llm_model_id())
    await rate_limiter.check_cost_budget(request, _code_llm_model_id())
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are an expert {payload.language} developer. "
        "Explain what the following code does, step by step, in simple terms."
    )

    try:
        response = llm.generate(
            prompt=f"Code:\n{payload.code}\n\nExplanation:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        cleaned_response = _clean_repeated_content(response.strip())
        return CodeExplainResponse(explanation=cleaned_response)
    except Exception as e:
        logger.exception("Code explanation failed: %s", e)
        try:
            from backend.bedrock_llm import BedrockLLM
            from backend.config import config
            if llm.model_id != config.BEDROCK_MODEL_ID:
                fallback_llm = BedrockLLM(model_id=config.BEDROCK_MODEL_ID, region=config.AWS_REGION)
                response = fallback_llm.generate(
                    prompt=f"Code:\n{payload.code}\n\nExplanation:",
                    system_prompt=system_prompt,
                    max_tokens=2048,
                    temperature=0.3,
                )
                cleaned_response = _clean_repeated_content(response.strip())
                return CodeExplainResponse(explanation=cleaned_response)
        except Exception as fb_err:
            logger.exception("Fallback code explanation also failed: %s", fb_err)
        raise HTTPException(
            status_code=500, detail="Code explanation failed"
        )


@router.post("/debug", response_model=CodeDebugResponse)
@limiter.limit("40/hour")
async def debug_code(
    request: Request,
    payload: CodeDebugRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Debug and fix code issues using AWS Bedrock."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="code_debug")
    await rate_limiter.check_model_rate_limit(request, _code_llm_model_id())
    await rate_limiter.check_cost_budget(request, _code_llm_model_id())
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are a skilled {payload.language} developer. "
        "Find and fix any bugs in the following code. "
        "Explain the problem and provide the corrected code."
    )

    try:
        response = llm.generate(
            prompt=f"Code:\n{payload.code}\n\nDebugging:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        analysis = _clean_repeated_content(response.strip())
        fixed_code = None

        if "```" in analysis:
            parts = analysis.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    lines = part.strip().split("\n")
                    if lines[0].lower() in SUPPORTED_LANGUAGES or lines[0] == "":
                        fixed_code = "\n".join(lines[1:] if lines[0] else lines)
                    else:
                        fixed_code = part.strip()
                    break

        if fixed_code:
            fixed_code = _extract_code(fixed_code)

        return CodeDebugResponse(analysis=analysis, fixed_code=fixed_code)
    except Exception as e:
        logger.exception("Debug code failed: %s", e)
        try:
            from backend.bedrock_llm import BedrockLLM
            from backend.config import config
            if llm.model_id != config.BEDROCK_MODEL_ID:
                fallback_llm = BedrockLLM(model_id=config.BEDROCK_MODEL_ID, region=config.AWS_REGION)
                response = fallback_llm.generate(
                    prompt=f"Code:\n{payload.code}\n\nDebugging:",
                    system_prompt=system_prompt,
                    max_tokens=2048,
                    temperature=0.3,
                )
                analysis = _clean_repeated_content(response.strip())
                fixed_code = None
                if "```" in analysis:
                    parts = analysis.split("```")
                    for i, part in enumerate(parts):
                        if i % 2 == 1:
                            lines = part.strip().split("\n")
                            if lines[0].lower() in SUPPORTED_LANGUAGES or lines[0] == "":
                                fixed_code = "\n".join(lines[1:] if lines[0] else lines)
                            else:
                                fixed_code = part.strip()
                            break
                if fixed_code:
                    fixed_code = _extract_code(fixed_code)
                return CodeDebugResponse(analysis=analysis, fixed_code=fixed_code)
        except Exception as fb_err:
            logger.exception("Fallback debug code also failed: %s", fb_err)
        raise HTTPException(status_code=500, detail="Code debugging failed")


@router.post("/chat", response_model=CodeChatResponse)
@limiter.limit("60/hour")
async def chat_with_code_llm(
    request: Request,
    payload: CodeChatRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Chat with AWS Bedrock for coding assistance."""
    await rate_limiter.check_rate_limit(request, limit=30, window=3600, scope="code_chat")
    await rate_limiter.check_model_rate_limit(request, _code_llm_model_id())
    await rate_limiter.check_cost_budget(request, _code_llm_model_id())
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    context = ""
    if payload.history:
        for msg in payload.history[-5:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context += f"{role.capitalize()}: {content}\n"

    system_prompt = (
        "You are an expert coding assistant. "
        "Your ONLY job is to help with programming, code, software development, and technical questions. "
        "If asked about anything unrelated to programming (phones, movies, weather, etc.), "
        "politely redirect to coding topics. "
        "Help debug code, explain algorithms, write functions, and discuss software architecture."
    )

    try:
        response = llm.generate(
            prompt=f"{context}User: {payload.message}\nAssistant:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.7,
        )
        cleaned_response = _clean_repeated_content(response.strip())
        return CodeChatResponse(response=cleaned_response)
    except Exception as e:
        logger.exception("Code chat failed: %s", e)
        try:
            from backend.bedrock_llm import BedrockLLM
            from backend.config import config
            if llm.model_id != config.BEDROCK_MODEL_ID:
                fallback_llm = BedrockLLM(model_id=config.BEDROCK_MODEL_ID, region=config.AWS_REGION)
                response = fallback_llm.generate(
                    prompt=f"{context}User: {payload.message}\nAssistant:",
                    system_prompt=system_prompt,
                    max_tokens=2048,
                    temperature=0.7,
                )
                cleaned_response = _clean_repeated_content(response.strip())
                return CodeChatResponse(response=cleaned_response)
        except Exception as fb_err:
            logger.exception("Fallback code chat also failed: %s", fb_err)
        raise HTTPException(status_code=500, detail="Chat request failed")


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported programming languages."""
    return {"languages": SUPPORTED_LANGUAGES}
