import streamlit as st
import traceback
import io
import contextlib
import subprocess
import tempfile
import os
from typing import Optional

from llama_index.llms.ollama import Ollama

SUPPORTED_LANGUAGES = ["python", "javascript", "java"]

# --- LLM Setup ---
CODE_LLM = Ollama(model="qwen2.5-coder:3b", request_timeout=120.0)

def generate_code(prompt: str, language: str = "python") -> str:
    system_prompt = (
        f"You are a helpful coding assistant. Write {language} code for the following request. "
        "Only output the code, no explanations or comments unless asked."
    )
    full_prompt = f"{system_prompt}\n\nRequest: {prompt}\n\nCode:"
    response = CODE_LLM.complete(full_prompt)
    return response.text.strip()

def explain_code(code: str, language: str = "python") -> str:
    system_prompt = (
        f"You are an expert {language} developer. Explain what the following code does, step by step, in simple terms."
    )
    full_prompt = f"{system_prompt}\n\nCode:\n{code}\n\nExplanation:"
    response = CODE_LLM.complete(full_prompt)
    return response.text.strip()

def debug_code(code: str, language: str = "python") -> str:
    system_prompt = (
        f"You are a skilled {language} developer. Find and fix any bugs in the following code. "
        "Explain the problem and provide the corrected code."
    )
    full_prompt = f"{system_prompt}\n\nCode:\n{code}\n\nDebugging:"
    response = CODE_LLM.complete(full_prompt)
    return response.text.strip()

def execute_python_code(code: str) -> str:
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": {**__builtins__.__dict__, "print": print}})
        return output.getvalue()
    except Exception:
        return f"Error during execution:\n{traceback.format_exc()}"

def execute_javascript_code(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        result = subprocess.run(["node", tmp_path], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error:\n{result.stderr}"
    except Exception as e:
        return f"Error running JavaScript: {e}"
    finally:
        os.remove(tmp_path)

def execute_java_code(code: str) -> str:
    # Wrap code in a class if not already
    class_name = "Main"
    if f"class {class_name}" not in code:
        code = f"public class {class_name} {{\npublic static void main(String[] args) {{\n{code}\n}}\n}}"
    with tempfile.TemporaryDirectory() as tmpdir:
        java_file = os.path.join(tmpdir, f"{class_name}.java")
        with open(java_file, "w") as f:
            f.write(code)
        try:
            compile_proc = subprocess.run(["javac", java_file], capture_output=True, text=True, timeout=10)
            if compile_proc.returncode != 0:
                return f"Compilation Error:\n{compile_proc.stderr}"
            run_proc = subprocess.run(["java", "-cp", tmpdir, class_name], capture_output=True, text=True, timeout=10)
            if run_proc.returncode == 0:
                return run_proc.stdout
            else:
                return f"Runtime Error:\n{run_proc.stderr}"
        except Exception as e:
            return f"Error running Java: {e}"

def execute_code(code: str, language: str) -> str:
    if language == "python":
        return execute_python_code(code)
    elif language == "javascript":
        return execute_javascript_code(code)
    elif language == "java":
        return execute_java_code(code)
    else:
        return "Unsupported language."

def render():
    st.title("🧑‍💻 Coding Agent Sandbox (Qwen2.5 Code)")

    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        st.markdown("### 🏖️ Code Sandbox")
        language = st.selectbox("Language", SUPPORTED_LANGUAGES, index=0)
        code_input = st.text_area(
            f"Write or paste your {language} code here:",
            height=220,
            key="sandbox_code_input"
        )

        run_btn = st.button("Run Code", use_container_width=True, key="run_code_btn")
        gen_btn = st.button("Generate Code", use_container_width=True, key="gen_code_btn")
        explain_btn = st.button("Explain Code", use_container_width=True, key="explain_code_btn")
        debug_btn = st.button("Debug Code", use_container_width=True, key="debug_code_btn")

        output = ""
        if run_btn:
            if code_input.strip():
                with st.spinner("Running code..."):
                    output = execute_code(code_input, language)
                st.markdown("**Output:**")
                st.code(output, language="text")
            else:
                st.warning("Please enter code to run.")

        if gen_btn:
            prompt = st.text_input("Describe what you want to code:", key="gen_prompt")
            if prompt.strip():
                with st.spinner("Generating code..."):
                    gen_code = generate_code(prompt, language)
                st.code(gen_code, language=language)
            else:
                st.warning("Please enter a prompt to generate code.")

        if explain_btn:
            if code_input.strip():
                with st.spinner("Explaining code..."):
                    explanation = explain_code(code_input, language)
                st.markdown(f"**Explanation:**\n\n{explanation}")
            else:
                st.warning("Please enter code to explain.")

        if debug_btn:
            if code_input.strip():
                with st.spinner("Debugging code..."):
                    debugged = debug_code(code_input, language)
                st.markdown(debugged)
            else:
                st.warning("Please enter code to debug.")

    with col2:
        st.markdown("### 💬 Chat with Coding LLM")
        if "code_chat_history" not in st.session_state:
            st.session_state.code_chat_history = []
        chat_input = st.text_area("Type your message to the coding LLM:", key="chat_input", height=100)
        if st.button("Send", key="send_chat_btn"):
            if chat_input.strip():
                with st.spinner("Thinking..."):
                    chat_response = CODE_LLM.complete(chat_input).text.strip()
                st.session_state.code_chat_history.append(("user", chat_input))
                st.session_state.code_chat_history.append(("llm", chat_response))
            else:
                st.warning("Please enter a message.")

        # Display chat history
        for sender, msg in st.session_state.code_chat_history[-10:]:
            if sender == "user":
                st.markdown(f"<div style='background:#e3f2fd;padding:8px 12px;border-radius:8px;margin-bottom:4px;text-align:right;'><b>You:</b> {msg}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background:#f1f8e9;padding:8px 12px;border-radius:8px;margin-bottom:4px;'><b>LLM:</b> {msg}</div>", unsafe_allow_html=True)