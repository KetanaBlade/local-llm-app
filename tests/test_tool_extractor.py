import json
import re
from typing import List, Dict, Any

def extract_tool_calls(msg_obj: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
    """
    Extracts tool calls from an Ollama response object.
    Supports:
    1. Native `msg_obj['tool_calls']`
    2. Raw JSON objects in `msg_obj['content']`
    3. Markdown-fenced JSON blocks (```json ... ```)
    4. `<tool_call> ... </tool_call>` tags
    5. Formats with `parameters` or `arguments`

    Returns:
        (tool_calls, remaining_content)
    """
    native_calls = msg_obj.get("tool_calls") or []
    if native_calls:
        # Standardize native calls to ensure 'arguments' is a dict
        normalized = []
        for tc in native_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            normalized.append({
                "id": tc.get("id"),
                "function": {
                    "name": fn.get("name"),
                    "arguments": args
                }
            })
        return normalized, msg_obj.get("content", "")

    content = msg_obj.get("content", "")
    if not content:
        return [], ""

    valid_tool_names = {
        "execute_python", "run_python_sandbox",
        "read_file", "edit_file_content",
        "list_directory", "generate_visual_media",
        "search_web"
    }

    found_calls = []
    clean_text = content

    # Check for <tool_call>...</tool_call>
    tool_call_tags = re.findall(r"<tool_call>([\s\S]*?)</tool_call>", content)
    for tag_body in tool_call_tags:
        try:
            parsed = json.loads(tag_body.strip())
            name = parsed.get("name")
            args = parsed.get("arguments") or parsed.get("parameters") or {}
            if name in valid_tool_names:
                found_calls.append({"function": {"name": name, "arguments": args}})
                clean_text = clean_text.replace(f"<tool_call>{tag_body}</tool_call>", "")
        except Exception:
            pass

    if found_calls:
        return found_calls, clean_text.strip()

    # Check for markdown code fences ```json ... ``` or ``` ... ```
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    for block in code_blocks:
        block_trimmed = block.strip()
        if block_trimmed.startswith("{") and block_trimmed.endswith("}"):
            try:
                parsed = json.loads(block_trimmed)
                name = parsed.get("name")
                args = parsed.get("arguments") or parsed.get("parameters") or {}
                if name in valid_tool_names:
                    found_calls.append({"function": {"name": name, "arguments": args}})
                    clean_text = clean_text.replace(f"```{block}```", "")
            except Exception:
                pass

    if found_calls:
        return found_calls, clean_text.strip()

    # Check for raw JSON object in content (e.g. `{"name":"execute_python","parameters":{...}}`)
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            name = parsed.get("name")
            args = parsed.get("arguments") or parsed.get("parameters") or {}
            if name in valid_tool_names:
                found_calls.append({"function": {"name": name, "arguments": args}})
                return found_calls, ""
        except Exception:
            pass

    # Regex find any JSON object containing "name": "<tool_name>"
    json_candidates = re.finditer(r"(\{[\s\S]*?\"name\"\s*:\s*\"([a-zA-Z0-9_-]+)\"[\s\S]*?\})", content)
    for m in json_candidates:
        full_match = m.group(1)
        name = m.group(2)
        if name in valid_tool_names:
            try:
                parsed = json.loads(full_match)
                args = parsed.get("arguments") or parsed.get("parameters") or {}
                found_calls.append({"function": {"name": name, "arguments": args}})
                clean_text = clean_text.replace(full_match, "")
            except Exception:
                pass

    return found_calls, clean_text.strip()

# Test with the exact string from the screenshot!
sample1 = '{"name":"execute_python","parameters":{"script":"import openpyxl\\nopenpyxl.load_workbook(\\"budget.xlsx\\")\\n# Add new row to sheet 1\\nsheet1[\'A1\'] = \\"New Value\\""}}'
calls1, text1 = extract_tool_calls({"role": "assistant", "content": sample1})
print("Test 1 Result:", calls1)
assert len(calls1) == 1
assert calls1[0]["function"]["name"] == "execute_python"
assert "openpyxl.load_workbook" in calls1[0]["function"]["arguments"]["script"]
print("Test 1 Passed!")

# Test with qwen2.5-coder screenshot string!
sample2 = '{"name":"execute_python","parameters":{"script":"import openpyxl\\nwb = openpyxl.load_workbook(\\"budget.xlsx\\")\\nsheet1 = wb[\\"Sheet1\\"]\\nsheet1[\'A1\'] = \'New Value\'\\nwb.save(\\"budget_updated.xlsx\\")"}}'
calls2, text2 = extract_tool_calls({"role": "assistant", "content": sample2})
print("Test 2 Result:", calls2)
assert len(calls2) == 1
assert calls2[0]["function"]["name"] == "execute_python"
print("Test 2 Passed!")
