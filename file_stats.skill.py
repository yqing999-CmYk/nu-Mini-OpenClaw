"""
name: file_stats
description: Report file counts and sizes for the project workspace
version: "1.0"
"""
from pathlib import Path


async def run(workspace: Path, **kwargs) -> str:
    if not workspace.exists():
        return "Workspace directory does not exist."

    all_items = list(workspace.rglob("*"))
    files = [f for f in all_items if f.is_file()]

    if not files:
        return "No files found in workspace."

    total_size = sum(f.stat().st_size for f in files)

    by_ext: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower() if f.suffix else "(no ext)"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    lines = [
        f"Total files : {len(files)}",
        f"Total size  : {total_size:,} bytes  ({total_size / 1024:.1f} KB)",
        "",
        "By extension:",
    ]
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        lines.append(f"  {ext:<12} {count} file{'s' if count != 1 else ''}")

    return "\n".join(lines)
