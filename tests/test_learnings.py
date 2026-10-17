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


def test_sd_multi_model_router():
    from backend.tools import list_available_sd_models, resolve_sd_model_and_prompts

    models = list_available_sd_models()
    print(f"[TEST] Discovered {len(models)} diffusion models:")
    for m in models.values():
        print(f"  - {m['label']} ({m['filename']}, {m['size_gb']} GB)")

    assert len(models) >= 3, f"Expected at least 3 models, got {len(models)}"

    # 1. Test Photorealism routing
    p_model, p_style, p_prompt, p_neg, p_engine = resolve_sd_model_and_prompts(
        "a candid 35mm photo of a barista pouring coffee, real life, realistic",
        requested_style="auto",
    )
    assert p_style == "photorealistic"
    assert "realistic" in p_model.name.lower()
    assert "raw photo" in p_prompt
    assert "drawing" in p_neg
    print(f"[PASS] Photorealism routed to: {p_model.name} ({p_engine})")

    # 2. Test Anime routing
    a_model, a_style, a_prompt, a_neg, a_engine = resolve_sd_model_and_prompts(
        "kawaii magical girl with glowing staff in an anime city street, studio ghibli aesthetic",
        requested_style="auto",
    )
    assert a_style == "anime"
    assert "meina" in a_model.name.lower()
    assert "anime" in a_prompt
    assert "photorealistic" in a_neg
    print(f"[PASS] Anime routed to: {a_model.name} ({a_engine})")

    # 3. Test Artistic / Concept Art routing
    c_model, c_style, c_prompt, c_neg, c_engine = resolve_sd_model_and_prompts(
        "ancient floating obsidian monolith above a crystalline lake at sunset, concept art",
        requested_style="auto",
    )
    assert c_style == "artistic"
    assert "dreamshaper" in c_model.name.lower()
    print(f"[PASS] Artistic routed to: {c_model.name} ({c_engine})")

    # 4. Test Explicit requested_style override
    o_model, o_style, _, _, _ = resolve_sd_model_and_prompts(
        "cyberpunk street",
        requested_style="photorealistic",
    )
    assert o_style == "photorealistic"
    assert "realistic" in o_model.name.lower()
    print("[PASS] Explicit style override works cleanly")

    # 5. Test Asking for model by name in prompt
    named_dream, _, _, _, _ = resolve_sd_model_and_prompts(
        "Use DreamShaper to create a realistic photo of a knight",
        requested_style="auto",
    )
    assert "dreamshaper" in named_dream.name.lower()
    print("[PASS] Named model 'DreamShaper' honored despite conflicting photo keyword")

    named_meina, _, _, _, _ = resolve_sd_model_and_prompts(
        "Use MeinaMix to generate a portrait of an astronaut",
        requested_style="auto",
    )
    assert "meina" in named_meina.name.lower()
    print("[PASS] Named model 'MeinaMix' honored directly")

    named_cyber, _, _, _, _ = resolve_sd_model_and_prompts(
        "Use CyberRealistic to create a portrait of a doctor",
        requested_style="auto",
    )
    assert "cyberrealistic" in named_cyber.name.lower()
    print("[PASS] Named model 'CyberRealistic' honored directly")


def test_artifact_lifecycle():
    import asyncio
    from backend.database import (
        init_db, create_conversation, add_message, register_artifact,
        delete_artifact, get_conversation, ARTIFACTS_DIR
    )

    async def _run():
        await init_db()
        conv = await create_conversation(title="Test Artifact Purge", model="test", mode="agent")
        cid = conv["id"]

        test_file = ARTIFACTS_DIR / "test_purge_file.png"
        test_file.write_bytes(b"dummy image bytes")

        art = await register_artifact(
            title="Test Purge",
            filename=test_file.name,
            category="image",
            mime_type="image/png",
            size_bytes=len(b"dummy image bytes"),
            conversation_id=cid,
        )

        msg = await add_message(
            conversation_id=cid,
            role="assistant",
            content="Here is your file.",
            artifacts=[art],
        )

        # 1. Before deletion, get_conversation must return the artifact
        loaded_before = await get_conversation(cid)
        assert len(loaded_before["messages"][-1]["artifacts"]) == 1

        # 2. Obliterate artifact
        res = await delete_artifact(art["id"])
        assert res["status"] == "obliterated"
        assert not test_file.exists(), "File should be unlinked from disk"

        # 3. After deletion, get_conversation must NOT return the artifact
        loaded_after = await get_conversation(cid)
        assert len(loaded_after["messages"][-1]["artifacts"]) == 0, "Deleted artifact must be filtered out"

        print("[PASS] test_artifact_lifecycle: verified complete purge from messages and disk")

    asyncio.run(_run())


if __name__ == "__main__":
    test_confine_to_workspace()
    test_date_grounding()
    test_context_compaction()
    test_sd_multi_model_router()
    test_artifact_lifecycle()
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
