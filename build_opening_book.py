import argparse
import json
import os
import random
import time

from Agents.OpeningBook import pvs, mirror_board, append_to_book_jsonl
from Agents.foundation import encode, is_win

# File này dùng để sinh Opening Book.
# Ý tưởng:
# - Sinh nhiều trạng thái hợp lệ (ngẫu nhiên + bias center) trong những ply đầu.
# - Với mỗi trạng thái, chạy PVS ở depth cao (không giới hạn thời gian) để tìm best move.
# - Ghi ra file dữ liệu dạng JSONL (append nhanh, không rewrite cả file mỗi entry).
# - (Tuỳ chọn) compile JSONL -> JSON mapping để load nhanh hơn.


MOVE_ORDER = [3, 2, 4, 1, 5, 0, 6]


def _board_is_full(board_list):
    return all(v != 0 for v in board_list)


def _valid_moves_from_board(board_list):
    # Kaggle board is row-major from top row; column is full iff top cell is non-zero.
    return [c for c in MOVE_ORDER if board_list[c] == 0]


def _apply_move_1d(board_list, col, mark):
    """Drop a piece into a column on a 1D kaggle board list (len=42).

    Indexing: idx = row * 7 + col, row=0 is top.
    """
    for row in range(5, -1, -1):
        idx = row * 7 + col
        if board_list[idx] == 0:
            board_list[idx] = mark
            return True
    return False


def _random_position(rng: random.Random, max_plies: int):
    """Generate a random *legal* early-game position.

    Returns: (board_list, mark_to_move)
    """
    board = [0] * 42
    plies = rng.randint(0, max_plies)
    mark = 1

    for _ in range(plies):
        moves = _valid_moves_from_board(board)
        if not moves:
            break
        # Bias toward center but still random.
        col = moves[rng.randrange(len(moves))]
        _apply_move_1d(board, col, mark)

        # Stop early on terminal state to avoid wasting time.
        me_bb, opp_bb = encode(board, mark)
        if is_win(me_bb):
            break
        mark = 2 if mark == 1 else 1

    # Next player to move
    return board, mark


def _canonical_state_and_move(me: int, opp: int, move: int):
    """Use mirror symmetry to reduce duplicate book entries.

    Store the lexicographically smaller of (me,opp) and mirrored state.
    If mirrored is chosen, convert move -> (6 - move).
    """
    m_me = mirror_board(me)
    m_opp = mirror_board(opp)
    if (m_me, m_opp) < (me, opp):
        return m_me, m_opp, 6 - move
    return me, opp, move

def analyze_and_append_entry(board_list, mark, depth_limit, out_jsonl, seen=None):
    """
    board_list: mảng 42 ô (hoặc tuple board trạng thái cần phân tích).
    mark: lượt của ta (1 hoặc 2).
    depth_limit: độ sâu PVS mong muốn (càng cao càng tốn thời gian nhưng càng mạnh).
    """
    me, opp = encode(board_list, mark)
    deadline = INF  # Bỏ qua giới hạn thời gian

    # Chạy logic search tại Root Node
    valid_moves = _valid_moves_from_board(board_list)
    if not valid_moves or _board_is_full(board_list):
        return False

    # Skip terminal (already won/lost) states.
    if is_win(me) or is_win(opp):
        return False

    best_score = NNF
    best_move = valid_moves[0]
    
    # Root search for each candidate move
    for col in valid_moves:
        col_mask = 0b111111 << (col * 7)
        occupied = (me | opp) & col_mask
        new_piece = (occupied + (1 << (col * 7))) & col_mask
        
        score = -pvs(opp, me | new_piece, depth_limit, NNF, INF, deadline)
        if score > best_score:
            best_score = score
            best_move = col
            
        # Nếu thắng ngay thì chốt luôn
        if best_score == INF:
            break

    me_c, opp_c, move_c = _canonical_state_and_move(me, opp, best_move)

    if seen is not None:
        key = (me_c, opp_c)
        if key in seen:
            return False
        seen.add(key)

    append_to_book_jsonl(me_c, opp_c, move_c, path=out_jsonl)
    return True


def compile_jsonl_to_json(in_jsonl: str, out_json: str):
    """Compile JSONL entries into a single JSON mapping file.

    If the same (me,opp) appears multiple times, the last entry wins.
    """
    mapping = {}
    with open(in_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            me = int(obj["me"])
            opp = int(obj["opp"])
            move = int(obj["move"])
            mapping[f"{me},{opp}"] = move

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ConnectX opening book entries using deep PVS.")
    parser.add_argument("--positions", type=int, default=5000, help="How many positions to generate.")
    parser.add_argument("--max-plies", type=int, default=8, help="Max random plies before evaluating.")
    parser.add_argument("--depth", type=int, default=14, help="PVS depth for evaluation (higher = slower/stronger).")
    parser.add_argument(
        "--output-jsonl",
        default=os.path.join("Agents", "opening_book.jsonl"),
        help="Output JSONL path (append-only).",
    )
    parser.add_argument(
        "--compile-json",
        default=None,
        help="If set, compile JSONL into a single JSON mapping at the end.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    parser.add_argument("--seen-cap", type=int, default=200000, help="Max in-memory seen set size to reduce duplicates.")
    args = parser.parse_args()

    start = time.time()
    rng = random.Random(args.seed)

    out_jsonl = args.output_jsonl
    # If relative path, anchor to repo root (this file's directory).
    if not os.path.isabs(out_jsonl):
        out_jsonl = os.path.join(os.path.dirname(__file__), out_jsonl)
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)

    print("====================================")
    print(" OPENING BOOK GENERATOR (JSONL)")
    print("====================================")
    print(f"positions={args.positions}  max_plies={args.max_plies}  depth={args.depth}")
    print(f"output={out_jsonl}")

    seen = set()
    written = 0
    attempted = 0

    while written < args.positions:
        attempted += 1
        if len(seen) > args.seen_cap:
            seen.clear()

        board, mark = _random_position(rng, args.max_plies)
        ok = analyze_and_append_entry(board, mark, args.depth, out_jsonl, seen=seen)
        if ok:
            written += 1

        if written > 0 and written % 200 == 0:
            elapsed = time.time() - start
            print(f"written={written} attempted={attempted} elapsed={elapsed:.1f}s")

    elapsed = time.time() - start
    print(f"Done. written={written} attempted={attempted} elapsed={elapsed:.1f}s")

    if args.compile_json:
        out_json = args.compile_json
        if not os.path.isabs(out_json):
            out_json = os.path.join(os.path.dirname(__file__), out_json)
        print(f"Compiling JSONL -> JSON: {out_json}")
        compile_jsonl_to_json(out_jsonl, out_json)
