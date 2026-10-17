import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent import extract_tool_calls

def test_extract_tool_calls_variations():
    print("=== Testing extract_tool_calls variations ===")

    # Test 1: Native tool calls
    native = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_123",
                "function": {
                    "name": "execute_python",
                    "arguments": {"script": "print('hello')"}
                }
            }
        ]
    }
    calls, text = extract_tool_calls(native)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "execute_python"
    assert calls[0]["function"]["arguments"]["script"] == "print('hello')"
    print("[PASS] Native tool calls")

    # Test 2: Text JSON with 'parameters' (Qwen / Llama raw format)
    text_param = {
        "role": "assistant",
        "content": '{"name":"execute_python","parameters":{"script":"import openpyxl\\nwb = openpyxl.Workbook()"}}'
    }
    calls, text = extract_tool_calls(text_param)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "execute_python"
    assert "openpyxl.Workbook" in calls[0]["function"]["arguments"]["script"]
    print("[PASS] Text JSON with 'parameters'")

    # Test 3: Markdown code fence with JSON
    text_fence = {
        "role": "assistant",
        "content": "Let me create that for you:\n```json\n{\n  \"name\": \"execute_python\",\n  \"arguments\": {\"script\": \"print('fenced')\"}\n}\n```\nDone."
    }
    calls, text = extract_tool_calls(text_fence)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "execute_python"
    print("[PASS] Markdown fenced JSON tool call")

    # Test 4: Pure conversational text with no tool call
    conversational = {
        "role": "assistant",
        "content": "Yes, I can certainly edit an Excel file for you! Please provide the file path or upload it, and I will inspect it using openpyxl."
    }
    calls, text = extract_tool_calls(conversational)
    assert len(calls) == 0
    assert "Yes, I can certainly edit" in text
    print("[PASS] Pure conversational text")

    print("ALL TOOL EXTRACTOR TESTS PASSED!")

if __name__ == "__main__":
    test_extract_tool_calls_variations()
