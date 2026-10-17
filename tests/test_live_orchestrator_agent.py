import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent import run_agent_stream

async def run_live_tests():
    print("=== TEST 1: Conversational question in Orchestrator Mode ===")
    events1 = []
    async for ev in run_agent_stream(
        conversation_id="test_conv_conv",
        history_messages=[],
        user_prompt="can you edit an excel file?",
        model="qwen2.5-coder:7b",
        mode="agent",
        hw_profile={},
        offline_mode=True,
    ):
        events1.append(ev)

    done_ev1 = next((e for e in events1 if e.get("type") == "done"), None)
    tool_calls1 = done_ev1.get("tool_calls", []) if done_ev1 else []
    content1 = done_ev1.get("content", "") if done_ev1 else ""

    print("Test 1 Tool Calls Count:", len(tool_calls1))
    print("Test 1 Response Content Preview:", content1[:150])
    # The agent should respond conversationally without calling a dummy tool
    assert len(tool_calls1) == 0, f"Expected 0 tool calls for conversational question, got: {tool_calls1}"
    assert "excel" in content1.lower() or "file" in content1.lower(), "Expected helpful conversational answer about Excel"
    print("[PASS] Test 1: Conversational inquiry answered naturally without hallucinating dummy files!\n")

    print("=== TEST 2: Actionable Excel creation in Orchestrator Mode ===")
    events2 = []
    async for ev in run_agent_stream(
        conversation_id="test_conv_act",
        history_messages=[],
        user_prompt="Please create an excel spreadsheet called test_agent_fruits.xlsx with Columns: Fruit, Price, Stock. Add 3 rows.",
        model="qwen2.5-coder:7b",
        mode="agent",
        hw_profile={},
        offline_mode=True,
    ):
        events2.append(ev)

    done_ev2 = next((e for e in events2 if e.get("type") == "done"), None)
    tool_calls2 = done_ev2.get("tool_calls", []) if done_ev2 else []
    content2 = done_ev2.get("content", "") if done_ev2 else ""
    artifacts2 = done_ev2.get("artifacts", []) if done_ev2 else []

    print("Test 2 Tool Calls Count:", len(tool_calls2))
    print("Test 2 Artifacts Count:", len(artifacts2))
    print("Test 2 Response Content Preview:", content2[:150])
    assert len(tool_calls2) >= 1, "Expected agent to call a tool to create the Excel file"
    assert len(artifacts2) >= 1 or any(tc.get("status") == "success" for tc in tool_calls2), "Tool execution succeeded"
    print("[PASS] Test 2: Agent autonomously invoked tool and completed Excel task!\n")

if __name__ == "__main__":
    asyncio.run(run_live_tests())
