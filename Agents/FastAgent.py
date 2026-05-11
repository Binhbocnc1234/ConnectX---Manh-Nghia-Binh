"""
FastAgent.py - Python bridge to C++ engine.

Giao tiep voi C++ qua stdin/stdout subprocess:
  Python -> C++: "<me_hex> <opp_hex> <deadline_ms>\\n"
  C++    -> Python: "<best_col>\\n"

De su dung:
  env.run([FastAgent.agent, opponent])
"""
import subprocess
import os
import time

try:
    import Output.log_system as log_system
except Exception:
    log_system = None

_PROC = None


def _find_engine():
    """Tim file engine.exe (Windows) hoac engine (Linux)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for name in ("engine.exe", "engine"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def _get_engine():
    """Lay subprocess engine, khoi dong neu chua chay."""
    global _PROC
    if _PROC is None or _PROC.poll() is not None:
        path = _find_engine()
        if path is None:
            raise FileNotFoundError(
                "[FastAgent] engine.exe not found. "
                "Compile: g++ -O3 -o Agents/engine.exe Agents/engine.cpp"
            )
        _PROC = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,   # None = pass-through to terminal (giup debug)
            text=True,
            bufsize=1,     # line-buffered
        )
    return _PROC


def encode(board, mark):
    """
    Chuyen board dang list (kaggle) sang hai bitboard (me, opp).

    Kaggle board: board[row*7 + col], row 0 = hang tren cung.
    Bitboard: bit col*7+row, row 0 = hang duoi cung (bottom).
    """
    me, opp = 0, 0
    rows, cols = 6, 7
    for col in range(cols):
        for row in range(rows):
            # Kaggle: row 0 = top  =>  bit row = bottom => kaggle_row = 5 - row
            kaggle_idx = (rows - 1 - row) * cols + col
            bit = col * 7 + row
            val = board[kaggle_idx]
            if val == mark:
                me  |= (1 << bit)
            elif val != 0:
                opp |= (1 << bit)
    return me, opp


def agent(obs, config):
    start = time.perf_counter()
    step  = obs.step

    me, opp = encode(obs.board, obs.mark)

    # Tinh deadline (ms tu Unix epoch)
    # Dung 1.8s co dinh + 1/3 overage (giu lai buffer an toan)
    base    = getattr(config, "timeout", 2)
    overage = getattr(obs,    "remainingOverageTime", 0)
    budget  = base * 0.88 + min(10.0, overage / 3.0)
    deadline = int((time.time() + budget) * 1000)

    col = 3  # fallback
    try:
        proc = _get_engine()
        proc.stdin.write(f"{me:016x} {opp:016x} {deadline}\n")
        proc.stdin.flush()
        col = int(proc.stdout.readline().strip())
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
