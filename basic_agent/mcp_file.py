"""
MCP server exposing filesystem administration tools for a restricted folder.
"""

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pathlib import Path
from typing import Any, Dict, List, Optional
import datetime
import fnmatch
import os
import sys

# Initialize the MCP server
mcp = FastMCP("filesystem-admin")

# Base directory configuration
ADMIN_ROOT_ENV = "FILESYSTEM_ADMIN_ROOT"
DEFAULT_ADMIN_ROOT = Path(
    r"C:\Users\User\Documents\facultate\Anul 4 TI1\sem1\ASO Oprisa\folder_de_administrat"
)


def _determine_base_dir() -> Path:
    """
    Resolve the administration root from the environment (or fallback path).
    """
    configured_path = os.environ.get(ADMIN_ROOT_ENV) or str(DEFAULT_ADMIN_ROOT)
    resolved = Path(configured_path).expanduser().resolve()

    if not resolved.exists():
        raise FileNotFoundError(
            f"The configured folder '{resolved}' does not exist "
            f"(set via {ADMIN_ROOT_ENV})."
        )
    if not resolved.is_dir():
        raise NotADirectoryError(
            f"The value '{resolved}' (set via {ADMIN_ROOT_ENV}) is not a directory."
        )
    return resolved


BASE_DIR = _determine_base_dir()
BASE_NAME = BASE_DIR.name.lower()


def _coerce_into_base(path: Path) -> Optional[Path]:
    """
    If the incoming path contains the base folder name later in the string,
    reconstruct a safe version rooted at BASE_DIR.
    """
    parts = list(path.parts)
    lowered = [p.lower() for p in parts]
    if BASE_NAME not in lowered:
        return None

    last_idx = len(parts) - 1 - lowered[::-1].index(BASE_NAME)
    suffix = parts[last_idx + 1:]
    candidate = BASE_DIR.joinpath(*suffix).resolve()

    try:
        candidate.relative_to(BASE_DIR)
    except Exception:
        return None
    return candidate


def _relative_display(path: Path) -> str:
    """
    Provide a readable path relative to the base directory.
    """
    try:
        rel = path.relative_to(BASE_DIR)
        rel_str = str(rel)
        return "." if rel_str == "." else rel_str
    except ValueError:
        return str(path)


def _format_value(value: Any) -> str:
    """
    Convert structured tool data into a readable string.
    """
    if isinstance(value, dict):
        if not value:
            return "(none)"
        return ", ".join(f"{k}={_format_value(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        if not value:
            return "(none)"
        return ", ".join(_format_value(v) for v in value)
    return str(value)


def function_make_response(summary: str, **data) -> ToolResult:
    """
    Build a ToolResult that provides human-friendly text plus structured metadata.
    This replaces the old _make_result to ensure the LLM gets a clear natural language description.
    """
    structured: Dict[str, object] = {"summary": summary}
    if data:
        structured["data"] = data

    # Construct a rich natural language response
    text_lines = [summary]
    
    # Add specific formatting based on the data keys to make it more "natural"
    if "entries" in data and isinstance(data["entries"], list):
        entries = data["entries"]
        if entries:
            text_lines.append("\nHere are the items found:")
            for entry in entries:
                text_lines.append(f"- {entry}")
        else:
            text_lines.append("\nThe directory is empty.")
            
    elif "content" in data and isinstance(data["content"], str):
        text_lines.append("\nFile Content:")
        text_lines.append("```")
        text_lines.append(data["content"])
        text_lines.append("```")
        
    elif "tree" in data and isinstance(data["tree"], list):
        text_lines.append("\nDirectory Structure:")
        text_lines.append("```")
        text_lines.extend(data["tree"])
        text_lines.append("```")
        
    elif "files" in data and isinstance(data["files"], list):
        text_lines.append("\nLarge Files Found:")
        for f in data["files"]:
            text_lines.append(f"- {f.get('path', 'unknown')} ({f.get('size_mb', 0)} MB)")
            
    elif "counts" in data and isinstance(data["counts"], list):
        text_lines.append("\nFile Counts by Extension:")
        for ext, count in data["counts"]:
            text_lines.append(f"- {ext}: {count}")
            
    # Fallback for generic data
    else:
        for key, value in data.items():
            # Skip keys we've already handled or that are redundant with summary
            if key in ["path", "summary", "entries", "content", "tree", "files", "counts"]:
                continue
            text_lines.append(f"- {key}: {_format_value(value)}")

    return ToolResult(
        content=[TextContent(type="text", text="\n".join(text_lines))],
        structured_content=structured,
    )


def _resolve_safe(p: str) -> Path:
    """
    Resolve a path inside BASE_DIR, preventing access outside the sandbox.
    """
    raw = Path(p)
    path = (BASE_DIR / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        path.relative_to(BASE_DIR)
    except Exception:
        fallback = _coerce_into_base(path)
        if fallback is None:
            raise ValueError(
                f"The path {path} is outside the managed directory {BASE_DIR}"
            )
        path = fallback
    return path


@mcp.tool()
def get_file_content(file_path: str) -> Dict[str, object]:
    """
    Read a UTF-8 text file from the managed directory.
    """
    path = _resolve_safe(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No file found at: {path}")
    rel = _relative_display(path)
    size = path.stat().st_size
    try:
        content = path.read_text(encoding="utf-8")
        summary = f"Successfully read {len(content.splitlines())} line(s) from '{rel}'."
        return function_make_response(
            summary,
            path=rel,
            size_bytes=size,
            is_text=True,
            content=content,
        )
    except UnicodeDecodeError:
        summary = f"The file '{rel}' is binary or not UTF-8 decodable."
        return function_make_response(
            summary, path=rel, size_bytes=size, is_text=False, content=None
        )


@mcp.tool()
def list_directory(dir_path: str = ".") -> Dict[str, object]:
    """
    List the items inside a directory.
    """
    path = _resolve_safe(dir_path)
    if not path.exists() or not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    for entry in path.iterdir():
        try:
            entries.append(entry.name + ("/" if entry.is_dir() else ""))
        except PermissionError:
            continue

    entries = sorted(entries)
    rel = _relative_display(path)
    count = len(entries)

    if not entries:
        summary = f"Directory '{rel}' is empty."
    else:
        summary = f"Directory '{rel}' contains {count} item(s)."

    return function_make_response(summary, path=rel, count=count, entries=entries)


@mcp.tool()
def get_file_info(file_path: str) -> Dict[str, object]:
    """
    Provide metadata about a file or directory.
    """
    path = _resolve_safe(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    rel = _relative_display(path)
    st = path.stat()
    kind = "directory" if path.is_dir() else "file"
    summary = f"Metadata retrieved for '{rel}'."
    return function_make_response(
        summary,
        path=rel,
        type=kind,
        size_bytes=st.st_size,
        modified=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
        created=datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
        absolute_path=str(path),
    )


@mcp.tool()
def search_files(pattern: str, dir_path: str = ".") -> Dict[str, object]:
    """
    Search for files or folders matching a glob pattern.
    """
    base = _resolve_safe(dir_path)
    if not base.exists() or not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    results: List[str] = []
    for item in base.rglob("*"):
        try:
            rel = item.relative_to(BASE_DIR)
        except ValueError:
            continue
        rel_str = str(rel)
        if fnmatch.fnmatch(rel_str, pattern):
            results.append(rel_str + ("/" if item.is_dir() else ""))

    results = sorted(results)
    rel_base = _relative_display(base)

    if not results:
        summary = f"No matches for '{pattern}' inside '{rel_base}'."
    else:
        summary = f"Found {len(results)} match(es) for '{pattern}' inside '{rel_base}'."

    return function_make_response(
        summary,
        base_path=rel_base,
        pattern=pattern,
        matches=results,
    )


@mcp.tool()
def get_directory_tree(dir_path: str = ".", max_depth: int = 3) -> Dict[str, object]:
    """
    Produce a textual directory tree up to the requested depth.
    """

    def _tree(current: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth >= max_depth:
            return []

        entries = []
        for entry in sorted(current.iterdir(), key=lambda e: e.name.lower()):
            if entry.name.startswith("."):
                continue
            entries.append(entry)

        lines: List[str] = []
        for idx, entry in enumerate(entries):
            is_last = idx == len(entries) - 1
            connector = "`-- " if is_last else "|-- "
            lines.append(
                f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}"
            )

            if entry.is_dir():
                extension = "    " if is_last else "|   "
                lines.extend(_tree(entry, prefix + extension, depth + 1))

        return lines

    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    rel = _relative_display(base)
    tree_lines = [f"{rel}/"]
    tree_lines.extend(_tree(base))
    summary = f"Generated tree for '{rel}' up to depth {max_depth}."
    return function_make_response(summary, path=rel, max_depth=max_depth, tree=tree_lines)


@mcp.tool()
def get_disk_usage(dir_path: str = ".") -> Dict[str, object]:
    """
    Summarize disk usage for a directory and its descendants.
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    total_size = 0
    file_count = 0
    dir_count = 0

    for item in base.rglob("*"):
        try:
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
            elif item.is_dir():
                dir_count += 1
        except (PermissionError, FileNotFoundError):
            continue

    size_mb = round(total_size / 1024 / 1024, 2)
    rel = _relative_display(base)
    summary = f"Calculated disk usage for '{rel}'."
    return function_make_response(
        summary,
        path=rel,
        size_bytes=total_size,
        size_mb=size_mb,
        file_count=file_count,
        dir_count=dir_count,
    )


@mcp.tool()
def find_large_files(
    dir_path: str = ".", min_size_mb: float = 1.0, limit: int = 10
) -> Dict[str, object]:
    """
    List the largest files above a minimum size within a directory.
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    min_size_bytes = min_size_mb * 1024 * 1024
    files = []

    for item in base.rglob("*"):
        try:
            if item.is_file():
                size = item.stat().st_size
                if size >= min_size_bytes:
                    files.append(
                        {
                            "path": str(item.relative_to(BASE_DIR)),
                            "size_bytes": size,
                            "size_mb": round(size / 1024 / 1024, 2),
                        }
                    )
        except (PermissionError, FileNotFoundError):
            continue

    files.sort(key=lambda x: x["size_mb"], reverse=True)
    files = files[:limit]

    rel = _relative_display(base)
    if not files:
        summary = f"No files >= {min_size_mb} MB found in '{rel}'."
    else:
        summary = (
            f"Top {len(files)} file(s) >= {min_size_mb} MB found in '{rel}'."
        )

    return function_make_response(
        summary,
        path=rel,
        min_size_mb=min_size_mb,
        limit=limit,
        files=files,
    )


@mcp.tool()
def count_files_by_extension(dir_path: str = ".") -> Dict[str, object]:
    """
    Count files grouped by extension.
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    counts: Dict[str, int] = {}

    for item in base.rglob("*"):
        try:
            if item.is_file():
                ext = item.suffix.lower() if item.suffix else "(no extension)"
                counts[ext] = counts.get(ext, 0) + 1
        except (PermissionError, FileNotFoundError):
            continue

    rel = _relative_display(base)
    if not counts:
        summary = f"No files detected under '{rel}'."
        sorted_counts: List[tuple[str, int]] = []
    else:
        summary = f"Counted files grouped by extension under '{rel}'."
        sorted_counts = sorted(
            counts.items(), key=lambda x: x[1], reverse=True)

    return function_make_response(summary, path=rel, counts=sorted_counts)


if __name__ == "__main__":
    print(f"[MCP] Running inside {BASE_DIR}", file=sys.stderr, flush=True)
    mcp.run()
