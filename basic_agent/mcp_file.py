"""
Server MCP pentru gestionarea unui director dat.
Expune tool-uri pentru a interacționa cu sistemul de fișiere.
"""

from fastmcp import FastMCP
from pathlib import Path
from typing import List
import sys
import json
import fnmatch
import datetime

# Inițializare server MCP
mcp = FastMCP("filesystem-admin")

# Directorul de bază pe care îl vom gestiona
BASE_DIR = Path(
    r"C:\Users\User\Documents\facultate\Anul 4 TI1\sem1\ASO Oprisa\folder_de_administrat"
).resolve()


def _resolve_safe(p: str) -> Path:
    """
    Rezolvă calea în interiorul BASE_DIR, prevenind accesul în afara directorului administrat.
    Acceptă căi relative sau absolute. Aruncă ValueError dacă iese din BASE_DIR.
    """
    raw = Path(p)
    path = (BASE_DIR / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        path.relative_to(BASE_DIR)
    except Exception:
        raise ValueError(
            f"Calea {path} este în afara directorului administrat {BASE_DIR}")
    return path


@mcp.tool()
def get_file_content(file_path: str) -> str:
    """
    Returnează conținutul unui fișier text (UTF-8) din directorul administrat.

    Args:
        file_path: Calea relativă (față de BASE_DIR) sau absolută către fișier.
    Returns:
        Conținutul fișierului ca șir de caractere.
    Raises:
        FileNotFoundError, PermissionError, UnicodeDecodeError, ValueError
    """
    path = _resolve_safe(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Nu există fișier: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # În cazul fișierelor binare, întoarcem informații de bază
        return f"<<Fișier binar / non-UTF8: {path.name}, dimensiune={path.stat().st_size} bytes>>"


@mcp.tool()
def list_directory(dir_path: str = ".") -> List[str]:
    """
    Listează conținutul unui director din directorul administrat.

    Args:
        dir_path: Calea relativă sau absolută a directorului (implicit: '.').
    Returns:
        Lista elementelor (nume fișiere/directoare) sortată alfabetic.
    Raises:
        NotADirectoryError, PermissionError, ValueError
    """
    path = _resolve_safe(dir_path)
    if not path.exists() or not path.is_dir():
        raise NotADirectoryError(f"Nu este director: {path}")
    entries = []
    for entry in path.iterdir():
        try:
            entries.append(entry.name + ("/" if entry.is_dir() else ""))
        except PermissionError:
            # Sare peste intrări inaccesibile
            continue
    return sorted(entries)


@mcp.tool()
def get_file_info(file_path: str) -> str:
    """
    Returnează metadate despre un fișier sau director ca JSON.

    Args:
        file_path: Calea relativă sau absolută.
    Returns:
        JSON string cu: name, path_rel, type, size, mtime, ctime.
    Raises:
        FileNotFoundError, ValueError
    """
    path = _resolve_safe(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Nu există: {path}")
    st = path.stat()
    info = {
        "name": path.name,
        "path_rel": str(path.relative_to(BASE_DIR)),
        "type": "dir" if path.is_dir() else "file",
        "size": st.st_size,
        "mtime": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
        "ctime": datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
    }
    return json.dumps(info, ensure_ascii=False)


@mcp.tool()
def search_files(pattern: str, dir_path: str = ".") -> List[str]:
    """
    Caută fișiere/directoare care se potrivesc cu un pattern (glob style).

    Args:
        pattern: Ex. '*.txt', 'subfolder/*.log', '*config*'
        dir_path: Directorul de pornire (implicit '.')
    Returns:
        Lista de căi relative (față de BASE_DIR) care se potrivesc.
    Raises:
        ValueError, NotADirectoryError
    """
    base = _resolve_safe(dir_path)
    if not base.exists() or not base.is_dir():
        raise NotADirectoryError(f"Nu este director: {base}")
    results: List[str] = []
    for p in base.rglob("*"):
        name = str(p.relative_to(base))
        if fnmatch.fnmatch(name, pattern):
            try:
                results.append(str(p.relative_to(BASE_DIR)))
            except Exception:
                # ar trebui să fie în BASE_DIR deja
                continue
    return sorted(results)

# ============== Tool-uri bonus ==============


@mcp.tool()
def get_directory_tree(dir_path: str = ".", max_depth: int = 3) -> str:
    """
    Generează o structură arborescentă a directorului (până la adâncimea max_depth).

    Args:
        dir_path: Calea relativă a directorului (implicit: '.')
        max_depth: Adâncimea maximă de explorare (implicit: 3)
    Returns:
        String formatat cu arborele de directoare
    """
    def _tree(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth > max_depth:
            return []

        lines = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (
                not p.is_dir(), p.name))
        except PermissionError:
            return [f"{prefix}[Permission Denied]"]

        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            lines.append(
                f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")

            if entry.is_dir() and depth < max_depth:
                extension = "    " if is_last else "│   "
                lines.extend(_tree(entry, prefix + extension, depth + 1))

        return lines

    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Nu este director: {base}")

    tree_lines = [str(base.relative_to(BASE_DIR)) + "/"]
    tree_lines.extend(_tree(base))
    return "\n".join(tree_lines)


@mcp.tool()
def get_disk_usage(dir_path: str = ".") -> str:
    """
    Calculează spațiul ocupat de un director și subdirectoarele sale.

    Args:
        dir_path: Calea relativă a directorului (implicit: '.')
    Returns:
        JSON string cu: path, total_size_mb, file_count, dir_count
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Nu este director: {base}")

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

    info = {
        'path': str(base.relative_to(BASE_DIR)),
        'total_size_mb': round(total_size / 1024 / 1024, 2),
        'file_count': file_count,
        'dir_count': dir_count
    }
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def find_large_files(dir_path: str = ".", min_size_mb: float = 1.0, limit: int = 10) -> str:
    """
    Găsește cele mai mari fișiere dintr-un director.

    Args:
        dir_path: Calea relativă a directorului (implicit: '.')
        min_size_mb: Dimensiunea minimă în MB (implicit: 10.0)
        limit: Numărul maxim de fișiere returnate (implicit: 10)
    Returns:
        JSON string cu lista fișierelor: path, size_mb
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Nu este director: {base}")

    min_size_bytes = min_size_mb * 1024 * 1024
    files = []

    for item in base.rglob("*"):
        try:
            if item.is_file():
                size = item.stat().st_size
                if size >= min_size_bytes:
                    files.append({
                        'path': str(item.relative_to(BASE_DIR)),
                        'size_mb': round(size / 1024 / 1024, 2)
                    })
        except (PermissionError, FileNotFoundError):
            continue

    files.sort(key=lambda x: x['size_mb'], reverse=True)
    return json.dumps(files[:limit], ensure_ascii=False, indent=2)


@mcp.tool()
def count_files_by_extension(dir_path: str = ".") -> str:
    """
    Numără fișierele din director grupate pe extensie.

    Args:
        dir_path: Calea relativă a directorului (implicit: '.')
    Returns:
        JSON string cu statistici: extensie -> count
    """
    base = _resolve_safe(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"Nu este director: {base}")

    counts: Dict[str, int] = {}

    for item in base.rglob("*"):
        try:
            if item.is_file():
                ext = item.suffix.lower() if item.suffix else "(no extension)"
                counts[ext] = counts.get(ext, 0) + 1
        except (PermissionError, FileNotFoundError):
            continue

    # Sortează descrescător după număr
    sorted_counts = dict(
        sorted(counts.items(), key=lambda x: x[1], reverse=True))
    return json.dumps(sorted_counts, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Atenție: nu printa pe stdout; dacă ai nevoie de debug, folosește stderr.
    print(f"[MCP] Pornit în {BASE_DIR}", file=sys.stderr, flush=True)
    mcp.run()
