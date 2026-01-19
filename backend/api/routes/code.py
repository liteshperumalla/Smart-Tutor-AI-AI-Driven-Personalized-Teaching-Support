"""Code sandbox API routes for code execution and LLM assistance."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
import traceback
import io
import contextlib
import subprocess
import tempfile
import os

from ..dependencies import get_current_user

router = APIRouter(prefix="/code", tags=["code"])

SUPPORTED_LANGUAGES = ["python", "javascript", "java"]


class CodeExecuteRequest(BaseModel):
    """Request to execute code."""

    code: str = Field(..., min_length=1, description="Code to execute")
    language: Literal["python", "javascript", "java"] = Field(
        default="python", description="Programming language"
    )


class CodeGenerateRequest(BaseModel):
    """Request to generate code from a prompt."""

    prompt: str = Field(
        ..., min_length=3, description="Description of what to generate"
    )
    language: Literal["python", "javascript", "java"] = Field(
        default="python", description="Target programming language"
    )


class CodeExplainRequest(BaseModel):
    """Request to explain code."""

    code: str = Field(..., min_length=1, description="Code to explain")
    language: Literal["python", "javascript", "java"] = Field(
        default="python", description="Programming language"
    )


class CodeDebugRequest(BaseModel):
    """Request to debug code."""

    code: str = Field(..., min_length=1, description="Code to debug")
    language: Literal["python", "javascript", "java"] = Field(
        default="python", description="Programming language"
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
    """Get the code LLM instance using AWS Bedrock (Llama 3.2)."""
    try:
        from backend.bedrock_llm import BedrockLLM
        from backend.config import config

        return BedrockLLM(
            model_id="us.meta.llama3-2-11b-instruct-v1:0", region=config.AWS_REGION
        )
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock LLM: {e}")
        return None


def _execute_python_code(code: str) -> tuple[str, bool]:
    """Execute Python code safely."""
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": __builtins__, "print": print})
        return output.getvalue(), True
    except Exception:
        return f"Error during execution:\n{traceback.format_exc()}", False


def _execute_javascript_code(code: str) -> tuple[str, bool]:
    """Execute JavaScript code using Node.js."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["node", tmp_path], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout or "(no output)", True
        else:
            return f"Error:\n{result.stderr}", False
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (10 seconds)", False
    except FileNotFoundError:
        return "Error: Node.js is not installed or not in PATH", False
    except Exception as e:
        return f"Error running JavaScript: {e}", False
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def _execute_java_code(code: str) -> tuple[str, bool]:
    """Execute Java code."""
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
            else:
                return f"Runtime Error:\n{run_proc.stderr}", False
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out (10 seconds)", False
        except FileNotFoundError:
            return "Error: Java is not installed or not in PATH", False
        except Exception as e:
            return f"Error running Java: {e}", False


def _execute_code(code: str, language: str) -> tuple[str, bool]:
    """Execute code in the specified language."""
    if language == "python":
        return _execute_python_code(code)
    elif language == "javascript":
        return _execute_javascript_code(code)
    elif language == "java":
        return _execute_java_code(code)
    else:
        return "Unsupported language.", False


@router.post("/execute", response_model=CodeExecuteResponse)
async def execute_code(
    request: CodeExecuteRequest,
    user: dict = Depends(get_current_user),
):
    """Execute code in the specified language."""
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
        f"You are a helpful coding assistant. Write {request.language} code for the following request. "
        "Only output the code, no explanations or comments unless asked. "
        "Do not include markdown code fences."
    )

    try:
        response = llm.generate(
            prompt=f"Request: {request.prompt}\n\nCode:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        code = response.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return CodeGenerateResponse(code=code, language=request.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")


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
        return CodeExplainResponse(explanation=response.strip())
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Code explanation failed: {str(e)}"
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
        analysis = response.strip()
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
        return CodeDebugResponse(analysis=analysis, fixed_code=fixed_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code debugging failed: {str(e)}")


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
        "You are a helpful coding assistant. Answer questions about programming, "
        "help debug code, explain concepts, and provide code examples when asked."
    )

    try:
        response = llm.generate(
            prompt=f"{context}User: {request.message}\nAssistant:",
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.7,
        )
        return CodeChatResponse(response=response.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported programming languages."""
    return {"languages": SUPPORTED_LANGUAGES}
