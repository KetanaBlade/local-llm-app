"""
Automated unit tests for Antigravity-style universal execution primitives:
1. Safe path resolution & backup creation
2. Universal file reader (Excel parsing & text line numbering)
3. Dynamic Python code execution (openpyxl Excel editing with auto-backup)
4. Directory explorer
5. Surgical text editing with .bak snapshot
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tools import (
    WORKSPACE_DIR,
    resolve_safe_path,
    create_file_backup,
    tool_read_file,
    tool_list_directory,
    tool_edit_file_content,
    tool_execute_python,
    get_tool_schemas,
)


async def run_tests():
    print("=== RUNNING ORCHESTRATOR PRIMITIVES TESTS ===")
    test_dir = WORKSPACE_DIR / "_test_orchestrator"
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Test 1: Path resolution & system path guards
        user_file = test_dir / "sample.txt"
        user_file.write_text("Line 1: Alpha\nLine 2: Beta\nLine 3: Gamma\n", encoding="utf-8")

        resolved = resolve_safe_path(str(user_file))
        assert resolved == user_file.resolve(), f"Path resolution mismatch: {resolved}"

        # Test Windows system directory guard
        system_blocked = False
        try:
            resolve_safe_path("C:/Windows/System32/drivers/etc/hosts")
        except PermissionError:
            system_blocked = True
        except Exception:
            pass
        if os.name == "nt":
            assert system_blocked, "Failed to block access to protected Windows system directory"
        print("[PASS] Test 1: Safe path resolution & OS directory guard")

        # Test 2: Backup creation
        bak = create_file_backup(user_file)
        assert bak is not None and bak.exists(), "Failed to create backup copy"
        assert bak.read_text(encoding="utf-8") == user_file.read_text(encoding="utf-8")
        print(f"[PASS] Test 2: Automatic backup creation -> {bak.name}")

        # Test 3: Read file (Text with line numbers)
        read_res = await tool_read_file(str(user_file), start_line=1, max_lines=10)
        assert read_res["status"] == "success"
        assert "1 | Line 1: Alpha" in read_res["content"]
        assert read_res["total_lines"] == 3
        print("[PASS] Test 3: Text file reading with line numbering")

        # Test 4: Excel Creation, Inspection, and Modification via Python Script
        excel_path = test_dir / "test_budget.xlsx"
        script_create = f"""
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Q3_Summary"
ws.append(["Category", "July", "August", "September", "Total"])
ws.append(["Revenue", 10000, 12000, 15000, "=SUM(B2:D2)"])
ws.append(["Payroll", -5000, -5000, -5000, "=SUM(B3:D3)"])
wb.save(r"{excel_path}")
print("Excel created successfully")
"""
        exec_res = await tool_execute_python(script=script_create, description="Create test excel")
        assert exec_res["status"] == "success", f"Failed creating Excel: {exec_res.get('stderr')}"
        assert excel_path.exists(), "Excel file was not created on disk"
        print("[PASS] Test 4A: Dynamic Python execution created Excel file")

        # Test 4B: tool_read_file on Excel (.xlsx) returns sheet names and markdown table
        read_excel_res = await tool_read_file(str(excel_path))
        assert read_excel_res["status"] == "success"
        assert read_excel_res["file_type"] == "excel"
        assert "Q3_Summary" in read_excel_res["sheets"]
        assert "Revenue" in read_excel_res["content"]
        print("[PASS] Test 4B: Excel workbook inspection & table extraction")

        # Test 4C: Modify existing Excel file with openpyxl and verify auto-backup
        script_modify = f"""
import openpyxl
wb = openpyxl.load_workbook(r"{excel_path}")
ws = wb["Q3_Summary"]
ws.append(["Marketing", -2000, -2500, -3000, "=SUM(B4:D4)"])
ws.append(["Net Profit", "=SUM(B2:B4)", "=SUM(C2:C4)", "=SUM(D2:D4)", "=SUM(E2:E4)"])
wb.save(r"{excel_path}")
print("Excel updated with Marketing and Net Profit rows")
"""
        mod_res = await tool_execute_python(
            script=script_modify,
            description="Update Excel with marketing and net profit",
            target_filepath=str(excel_path),
        )
        assert mod_res["status"] == "success", f"Modification failed: {mod_res.get('stderr')}"
        assert mod_res["backup_created"] is not None, "Auto-backup was not triggered for target_filepath"
        assert Path(mod_res["backup_created"]).exists(), "Backup file does not exist on disk"

        # Verify Excel content after update
        read_updated = await tool_read_file(str(excel_path))
        assert "Marketing" in read_updated["content"]
        assert "Net Profit" in read_updated["content"]
        print(f"[PASS] Test 4C: Excel file modified with auto-backup -> {Path(mod_res['backup_created']).name}")

        # Test 5: Surgical text replacement
        edit_res = await tool_edit_file_content(
            filepath=str(user_file),
            target_content="Line 2: Beta",
            replacement_content="Line 2: Beta (Updated via Orchestrator)",
        )
        assert edit_res["status"] == "success"
        assert "Updated via Orchestrator" in user_file.read_text(encoding="utf-8")
        print("[PASS] Test 5: Surgical text file editing with backup")

        # Test 6: Directory Explorer
        dir_res = await tool_list_directory(str(test_dir))
        assert dir_res["status"] == "success"
        assert len(dir_res["entries"]) >= 2
        print(f"[PASS] Test 6: Directory explorer found {dir_res['count']} entries")

        # Test 7: Schema verification
        schemas = get_tool_schemas(allow_web_search=True)
        schema_names = [s["function"]["name"] for s in schemas]
        assert "execute_python" in schema_names
        assert "read_file" in schema_names
        assert "edit_file_content" in schema_names
        assert "list_directory" in schema_names
        assert "search_web" in schema_names
        print(f"[PASS] Test 7: Universal primitive schemas verified ({len(schema_names)} tools registered)")

        print("\nALL 7 ORCHESTRATOR TESTS PASSED PERFECTLY!")
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_tests())
