import ctypes
import subprocess
from pathlib import Path
from threading import Lock

_ENGINE_LOCK = Lock()
_ENGINE_LIB = None


def _engine_paths():
    agents_dir = Path(__file__).resolve().parent
    source_path = agents_dir / "engine.cpp"
    library_path = agents_dir / "_engine.so"
    return agents_dir, source_path, library_path


def _build_engine_if_needed(source_path: Path, library_path: Path):
    if library_path.exists() and library_path.stat().st_mtime >= source_path.stat().st_mtime:
        return

    cmd = [
        "g++",
        "-std=c++20",
        "-O3",
        "-shared",
        "-fPIC",
        str(source_path),
        "-o",
        str(library_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(f"Failed to build C++ engine: {message}") from exc


def _load_engine():
    global _ENGINE_LIB
    if _ENGINE_LIB is not None:
        return _ENGINE_LIB

    with _ENGINE_LOCK:
        if _ENGINE_LIB is not None:
            return _ENGINE_LIB

        agents_dir, source_path, library_path = _engine_paths()
        _build_engine_if_needed(source_path, library_path)

        lib = ctypes.CDLL(str(library_path))
        lib.opening_book_opt_set_base_dir.argtypes = [ctypes.c_char_p]
        lib.opening_book_opt_set_base_dir.restype = None
        lib.opening_book_opt_agent.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_double,
            ctypes.c_int,
            ctypes.c_double,
        ]
        lib.opening_book_opt_agent.restype = ctypes.c_int
        lib.opening_book_opt_set_base_dir(str(agents_dir).encode("utf-8"))

        _ENGINE_LIB = lib
        return _ENGINE_LIB


def run_opening_book_opt(obs, config, timeout=2):
    lib = _load_engine()

    board = list(obs.board)
    board_size = len(board)
    board_array = (ctypes.c_int * board_size)(*board)

    timeout_has_value = 1 if timeout is not None else 0
    timeout_value = float(timeout if timeout is not None else getattr(config, "timeout", 2))

    has_overage = 1 if hasattr(obs, "remainingOverageTime") else 0
    overage_value = float(getattr(obs, "remainingOverageTime", 0))

    move = lib.opening_book_opt_agent(
        board_array,
        board_size,
        int(obs.mark),
        int(getattr(obs, "step", 0)),
        int(getattr(config, "columns", 7)),
        timeout_has_value,
        timeout_value,
        has_overage,
        overage_value,
    )
    return int(move)
