"""Code sandbox API routes for code execution and LLM assistance.

This module provides endpoints for:
- Code generation using AWS Bedrock Llama 3.2
- Code explanation and debugging
- Code-related chat assistance
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
import traceback
import io
import contextlib
import subprocess
import tempfile
import os

from ..dependencies import get_current_user, get_admin_session

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


def _get_code_llm():
    """Get the code LLM instance using AWS Bedrock (Llama 3.1 70B).

    Returns:
        BedrockLLM: Configured LLM instance or None if initialization fails.
    """
    try:
        from backend.bedrock_llm import BedrockLLM
        from backend.config import config

        return BedrockLLM(
            model_id="us.meta.llama3-1-70b-instruct-v1:0", region=config.AWS_REGION
        )
    except (ImportError, ValueError, RuntimeError):
        logger.exception("Failed to initialize Bedrock LLM")
        return None
    except Exception:
        logger.exception("Unexpected error initializing Bedrock LLM")
        return None
    except Exception:
        logger.exception("Unexpected error initializing Bedrock LLM")
        return None


def _execute_python_code(code: str) -> tuple[str, bool]:
    """Execute Python code.

    Note: This function is NOT sandboxed. Use only with trusted input.
    The exec() call has access to built-in functions like print().

    Args:
        code: Python code string to execute.

    Returns:
        Tuple of (output, success).
    """
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": __builtins__, "print": print})
        return output.getvalue(), True
    except SyntaxError:
        return f"Syntax Error:\n{traceback.format_exc()}", False
    except (NameError, TypeError, ValueError, AttributeError):
        return f"Runtime Error:\n{traceback.format_exc()}", False
    except Exception:
        return f"Error during execution:\n{traceback.format_exc()}", False


def _execute_javascript_code(code: str) -> tuple[str, bool]:
    """Execute JavaScript code using Node.js.

    Args:
        code: JavaScript code string to execute.

    Returns:
        Tuple of (output, success).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["node", tmp_path], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout or "(no output)", True
        return f"Error:\n{result.stderr}", False
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (10 seconds)", False
    except FileNotFoundError:
        return "Error: Node.js is not installed or not in PATH", False
    except OSError:
        return "Error: Unable to execute JavaScript (system error)", False
    except Exception:
        return f"Error running JavaScript:\n{traceback.format_exc()}", False
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _execute_java_code(code: str) -> tuple[str, bool]:
    """Execute Java code.

    Args:
        code: Java code string to execute.

    Returns:
        Tuple of (output, success).
    """
    class_name = "Main"
    if f"class {class_name}" not in code:
        code = f"public class {class_name} {{\npublic static void main(String[] args) {{\n{code}\n}}\n}}"

    with tempfile.TemporaryDirectory() as tmpdir:
        java_file = os.path.join(tmpdir, f"{class_name}.java")
        with open(java_file, "w") as f:
            f.write(code)
        try:
            compile_proc = subprocess.run(
                ["javac", java_file], capture_output=True, text=True, timeout=10
            )
            if compile_proc.returncode != 0:
                return f"Compilation Error:\n{compile_proc.stderr}", False

            run_proc = subprocess.run(
                ["java", "-cp", tmpdir, class_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if run_proc.returncode == 0:
                return run_proc.stdout or "(no output)", True
            return f"Runtime Error:\n{run_proc.stderr}", False
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out (10 seconds)", False
        except FileNotFoundError:
            return "Error: Java is not installed or not in PATH", False
        except OSError:
            return "Error: Unable to execute Java (system error)", False
        except Exception:
            return f"Error running Java:\n{traceback.format_exc()}", False


def _execute_typescript_code(code: str) -> tuple[str, bool]:
    """Execute TypeScript code using ts-node or compile to JS first.

    Args:
        code: TypeScript code string to execute.

    Returns:
        Tuple of (output, success).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as tmp:
        tmp.write(code)
        ts_path = tmp.name
    try:
        result = subprocess.run(
            ["npx", "ts-node", ts_path], capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return result.stdout or "(no output)", True
        return f"Error:\n{result.stderr}", False
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (15 seconds)", False
    except FileNotFoundError:
        return "Error: Node.js/TypeScript is not installed or not in PATH", False
    except OSError:
        return "Error: Unable to execute TypeScript (system error)", False
    except Exception:
        return f"Error running TypeScript:\n{traceback.format_exc()}", False
    finally:
        try:
            os.remove(ts_path)
        except OSError:
            pass


def _execute_cpp_code(code: str) -> tuple[str, bool]:
    """Execute C++ code using g++ compiler.

    Args:
        code: C++ code string to execute.

    Returns:
        Tuple of (output, success).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cpp_file = os.path.join(tmpdir, "main.cpp")
        with open(cpp_file, "w") as f:
            f.write(code)
        try:
            compile_proc = subprocess.run(
                ["g++", cpp_file, "-o", os.path.join(tmpdir, "main")],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if compile_proc.returncode != 0:
                return f"Compilation Error:\n{compile_proc.stderr}", False

            run_proc = subprocess.run(
                [os.path.join(tmpdir, "main")],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if run_proc.returncode == 0:
                return run_proc.stdout or "(no output)", True
            return f"Runtime Error:\n{run_proc.stderr}", False
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out (10 seconds)", False
        except FileNotFoundError:
            return "Error: g++ is not installed or not in PATH", False
        except OSError:
            return "Error: Unable to execute C++ (system error)", False
        except Exception:
            return f"Error running C++:\n{traceback.format_exc()}", False


def _execute_go_code(code: str) -> tuple[str, bool]:
    """Execute Go code using go run.

    Args:
        code: Go code string to execute.

    Returns:
        Tuple of (output, success).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".go", delete=False) as tmp:
        tmp.write(code)
        go_path = tmp.name
    try:
        result = subprocess.run(
            ["go", "run", go_path], capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return result.stdout or "(no output)", True
        return f"Error:\n{result.stderr}", False
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (15 seconds)", False
    except FileNotFoundError:
        return "Error: Go is not installed or not in PATH", False
    except OSError:
        return "Error: Unable to execute Go (system error)", False
    except Exception:
        return f"Error running Go:\n{traceback.format_exc()}", False
    finally:
        try:
            os.remove(go_path)
        except OSError:
            pass


def _execute_code(code: str, language: str) -> tuple[str, bool]:
    """Execute code in the specified language."""
    if language == "python":
        return _execute_python_code(code)
    elif language == "javascript":
        return _execute_javascript_code(code)
    elif language == "java":
        return _execute_java_code(code)
    elif language == "typescript":
        return _execute_typescript_code(code)
    elif language == "cpp":
        return _execute_cpp_code(code)
    elif language == "go":
        return _execute_go_code(code)
    else:
        return "Unsupported language.", False


@router.post("/execute", response_model=CodeExecuteResponse)
async def execute_code(
    request: CodeExecuteRequest,
    session=Depends(get_admin_session),
):
    """Execute code in the specified language. Admin-only."""
    output, success = _execute_code(request.code, request.language)
    return CodeExecuteResponse(
        output=output, success=success, error=None if success else output
    )


@router.post("/generate", response_model=CodeGenerateResponse)
async def generate_code(
    request: CodeGenerateRequest,
    user: dict = Depends(get_current_user),
):
    """Generate code from a natural language prompt."""
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are a helpful coding assistant. Write ONLY {request.language} code for the following request. "
        "Output ONLY the code in a single code block. "
        "Do NOT include explanations, comments, or any text before or after the code block."
    )

    try:
        response = llm.generate(
            prompt=f"Request: {request.prompt}\n\nCode:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        code = _extract_code(response.strip())
        return CodeGenerateResponse(code=code, language=request.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Code generation failed")


@router.post("/explain", response_model=CodeExplainResponse)
async def explain_code(
    request: CodeExplainRequest,
    user: dict = Depends(get_current_user),
):
    """Explain what the code does."""
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are an expert {request.language} developer. "
        "Explain what the following code does, step by step, in simple terms."
    )

    try:
        response = llm.generate(
            prompt=f"Code:\n{request.code}\n\nExplanation:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        cleaned_response = _clean_repeated_content(response.strip())
        return CodeExplainResponse(explanation=cleaned_response)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Code explanation failed"
        )


@router.post("/debug", response_model=CodeDebugResponse)
async def debug_code(
    request: CodeDebugRequest,
    user: dict = Depends(get_current_user),
):
    """Debug and fix code issues using AWS Bedrock."""
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    system_prompt = (
        f"You are a skilled {request.language} developer. "
        "Find and fix any bugs in the following code. "
        "Explain the problem and provide the corrected code."
    )

    try:
        response = llm.generate(
            prompt=f"Code:\n{request.code}\n\nDebugging:",
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
        logger.exception("Debug code failed")
        raise HTTPException(status_code=500, detail="Code debugging failed")


@router.post("/chat", response_model=CodeChatResponse)
async def chat_with_code_llm(
    request: CodeChatRequest,
    user: dict = Depends(get_current_user),
):
    """Chat with AWS Bedrock for coding assistance."""
    llm = _get_code_llm()
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="Code LLM is not available. Ensure AWS Bedrock is configured.",
        )

    context = ""
    if request.history:
        for msg in request.history[-5:]:
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
            prompt=f"{context}User: {request.message}\nAssistant:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.7,
        )
        cleaned_response = _clean_repeated_content(response.strip())
        return CodeChatResponse(response=cleaned_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Chat request failed")


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported programming languages."""
    return {"languages": SUPPORTED_LANGUAGES}
