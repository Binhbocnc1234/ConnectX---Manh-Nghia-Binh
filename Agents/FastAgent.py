"""
FastAgent.py - Python bridge to C++ engine shared library.

Gộp engine_bridge.py + FastAgent.py thành 1 file.
- Chỉ load C++ _engine.so đã build sẵn khi chạy agent
- Giữ helper build riêng để dùng thủ công khi cần

De su dung:
    env.run([FastAgent.agent, opponent])
"""
import ctypes
import subprocess
import time
from pathlib import Path
from threading import Lock

try:
    import Output.log_system as log_system
except Exception:
    log_system = None

_ENGINE_LOCK = Lock()
_ENGINE_LIB = None


def _engine_paths():
    agents_dir = Path(__file__).resolve().parent
    source_path = agents_dir / "engine.cpp"
    library_path = agents_dir / "engine.dll"
    return agents_dir, source_path, library_path


def _load_engine():
    global _ENGINE_LIB
    if _ENGINE_LIB is not None:
        return _ENGINE_LIB

    with _ENGINE_LOCK:
        if _ENGINE_LIB is not None:
            return _ENGINE_LIB

        agents_dir, _, library_path = _engine_paths()
        if not library_path.exists():
            raise FileNotFoundError(
                f"C++ engine library not found: {library_path}. "
                f"Build it once with build_engine_shared_library()."
            )

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
    """Gọi hàm C++ tính nước đi tối ưu."""
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


def agent(obs, config):
    """Hàm agent được gọi bởi Kaggle environment."""
    start = time.perf_counter()
    step = obs.step

    col = 3  # fallback
    try:
        col = run_opening_book_opt(obs, config, timeout=getattr(config, "timeout", 2))
    except Exception as e:
        print(f"[FastAgent] Engine error at step {step}: {e}")

    elapsed = time.perf_counter() - start
    print(f"[FastAgent] step={step} col={col} time={elapsed:.3f}s")

    if log_system:
        try:
            log_system.log_move("FastAgent", col, elapsed)
        except Exception:
            pass

    return col
