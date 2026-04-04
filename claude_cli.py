"""Wrapper for calling Claude via the Claude CLI (uses OAuth, no API key needed)."""

import subprocess
import json
import os
import shutil


def _find_claude_cli() -> str:
    """Find the claude CLI binary: PATH first, then local node_modules."""
    found = shutil.which("claude")
    if found:
        return found
    # Check local node_modules (installed by start.command)
    local = os.path.join(os.path.dirname(__file__), "node_modules", ".bin", "claude")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return "claude"  # fallback, will raise FileNotFoundError


def ask_claude(prompt: str, system_prompt: str = None, max_tokens: int = 4096, timeout: int = 300) -> str:
    """Send a prompt to Claude via the CLI and return the response text."""
    claude_bin = _find_claude_cli()
    cmd = [claude_bin, "--print"]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    cmd.extend(["--max-turns", "1"])

    # Pass the prompt via stdin
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Claude CLI error (exit {result.returncode}): {stderr}")

        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude CLI timed out after {timeout} seconds")
    except FileNotFoundError:
        raise RuntimeError(
            "Claude CLI not found. Install it: npm install -g @anthropic-ai/claude-code"
        )


def ask_claude_json(prompt: str, system_prompt: str = None, timeout: int = 300) -> dict:
    """Send a prompt to Claude and parse the response as JSON."""
    if system_prompt:
        system_prompt += "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no code fences, no explanation."
    else:
        system_prompt = "Respond with valid JSON only. No markdown, no code fences, no explanation."

    response = ask_claude(prompt, system_prompt=system_prompt, timeout=timeout)

    # Try to extract JSON from the response
    # Strip markdown code fences if present
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)
