"""
Unit tests for Odysseus-inspired core enhancements:
1. Workspace path confinement boundary (directory traversal defense)
2. Dynamic date & time grounding context
3. Cursor-style conversational context auto-compaction
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tools import confine_to_workspace, WORKSPACE_DIR
from backend.agent import get_current_date_context, compact_conversation_history, estimate_text_tokens


def test_confine_to_workspace():
    # Valid relative path inside workspace
    valid = confine_to_workspace("artifacts/report.xlsx")
    assert valid == (WORKSPACE_DIR / "artifacts" / "report.xlsx").resolve()

    # Block parent traversal attempts
    traversal_attempts = [
        "../../windows/system32/cmd.exe",
        "..\\..\\system.ini",
        "artifacts/../../secrets.txt",
    ]
    for attempt in traversal_attempts:
        blocked = False
        try:
            confine_to_workspace(attempt)
        except ValueError:
            blocked = True
        assert blocked, f"Failed to block traversal attempt: {attempt}"

    # Block NUL byte injections
    blocked_nul = False
    try:
        confine_to_workspace("artifacts/test\0.txt")
    except ValueError:
        blocked_nul = True
    assert blocked_nul, "Failed to block NUL byte injection"

    print("[PASS] test_confine_to_workspace")


def test_date_grounding():
    date_ctx = get_current_date_context()
    assert "Today's date is" in date_ctx
    assert "Ground all time-sensitive plans" in date_ctx
    print(f"[PASS] test_date_grounding: {date_ctx}")


def test_context_compaction():
    # 1. Short conversation should not compact
    short_history = [
        {"role": "user", "content": "How do I build a budget?"},
        {"role": "assistant", "content": "Start by listing income and fixed expenses."},
    ]
    res, notice = compact_conversation_history(short_history, num_ctx=4096)
    assert notice is None
    assert len(res) == 2

    # 2. Long conversation should compact older turns and preserve recent 4 turns verbatim
    long_history = []
    for i in range(12):
        long_history.append({"role": "user", "content": f"Turn {i} question: " + "context details " * 40})
        long_history.append({
            "role": "assistant",
            "content": f"Turn {i} answer: " + "actionable output " * 40,
            "artifacts": [{"filename": f"artifact_{i}.xlsx", "category": "spreadsheet"}] if i % 3 == 0 else []
        })

    compacted, notice = compact_conversation_history(long_history, num_ctx=1024)
    assert notice is not None
    assert "Auto-compacted" in notice
    assert compacted[0]["role"] == "system"
    assert "=== CONVERSATION ARCHIVE & RECAP" in compacted[0]["content"]
    assert "artifact_0.xlsx" in compacted[0]["content"]

    # Recent turns must be verbatim (last 4 items: 2 user + 2 assistant)
    assert compacted[-1]["content"] == long_history[-1]["content"]
    assert compacted[-2]["content"] == long_history[-2]["content"]
    assert compacted[-3]["content"] == long_history[-3]["content"]
    assert compacted[-4]["content"] == long_history[-4]["content"]

    print(f"[PASS] test_context_compaction: {notice}")


if __name__ == "__main__":
    test_confine_to_workspace()
    test_date_grounding()
    test_context_compaction()
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
