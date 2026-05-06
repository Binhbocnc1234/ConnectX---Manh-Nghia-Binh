import time
import log_system
from Agents.foundation import *
from Agents.heuristic import get_heuristic_bb

# https://grokipedia.com/page/Principal_variation_search
def _ordered_moves():
    """Uu tiên cột gần trung tâm"""
    return [3, 2, 4, 1, 5, 0, 6]

def mirror_board(bb):
    """Lật bitboard qua trục dọc"""
    m = 0
    m |= (bb & 0x7F) << 42          # Col 0 -> 6
    m |= (bb & (0x7F << 7)) << 28   # Col 1 -> 5
    m |= (bb & (0x7F << 14)) << 14  # Col 2 -> 4
    m |= (bb & (0x7F << 21))        # Col 3 -> 3
    m |= (bb & (0x7F << 28)) >> 14  # Col 4 -> 2
    m |= (bb & (0x7F << 35)) >> 28  # Col 5 -> 1
    m |= (bb & (0x7F << 42)) >> 42  # Col 6 -> 0
    return m

tt = {}  # Transposition Table
MAX_TT_SIZE = 1048576  # 2^20 slots

import os
import json

BOOK_FILE_JSON = os.path.join(os.path.dirname(__file__), "opening_book.json")
BOOK_FILE_JSONL = os.path.join(os.path.dirname(__file__), "opening_book.jsonl")

OPENING_BOOK = {}
_BOOK_LOADED = False


def _parse_key(key: str):
    me_s, opp_s = key.split(",")
    return int(me_s), int(opp_s)


def _key(me: int, opp: int) -> str:
    return f"{int(me)},{int(opp)}"


def load_book(force: bool = False):
    """Load opening book into memory.

    Supports 2 formats:
    - opening_book.json  : a single JSON object mapping "me,opp" -> move
    - opening_book.jsonl : JSON Lines, each line is {"me": int, "opp": int, "move": int}

    For large books, prefer JSONL during generation; runtime can still load either.
    """
    global OPENING_BOOK, _BOOK_LOADED
    if _BOOK_LOADED and not force:
        return

    OPENING_BOOK = {}
    # Prefer JSON (faster) if present; else fall back to JSONL.
    try:
        if os.path.exists(BOOK_FILE_JSON):
            with open(BOOK_FILE_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                me, opp = _parse_key(k)
                OPENING_BOOK[(me, opp)] = int(v)
            _BOOK_LOADED = True
            return

        if os.path.exists(BOOK_FILE_JSONL):
            with open(BOOK_FILE_JSONL, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    me = int(obj["me"])
                    opp = int(obj["opp"])
                    move = int(obj["move"])
                    OPENING_BOOK[(me, opp)] = move
            _BOOK_LOADED = True
            return

        _BOOK_LOADED = True
    except Exception as e:
        # Don't crash the agent if the book is malformed.
        print(f"Error loading opening book: {e}")
        _BOOK_LOADED = True


def append_to_book_jsonl(me: int, opp: int, move: int, path: str | None = None):
    """Append one entry to a JSONL book file (fast, no rewrite)."""
    if path is None:
        path = BOOK_FILE_JSONL
    entry = {"me": int(me), "opp": int(opp), "move": int(move)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")))
        f.write("\n")


def save_book_json(path: str | None = None):
    """Write the in-memory book to a single JSON mapping file."""
    if path is None:
        path = BOOK_FILE_JSON
    data = {_key(k[0], k[1]): int(v) for k, v in OPENING_BOOK.items()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def pvs(me, opp, depth, alpha, beta, deadline):
    state = (me, opp)
    state_hash = hash(state) % MAX_TT_SIZE

    # Kiểm tra xem dữ liệu về state có ở trong table không
    if state_hash in tt:
        stored_state, res, d = tt[state_hash]
        if stored_state == state and d >= depth:
            return res
            
    m_state = (mirror_board(me), mirror_board(opp))
    m_hash = hash(m_state) % MAX_TT_SIZE
    if m_hash in tt:
        stored_state, res, d = tt[m_hash]
        if stored_state == m_state and d >= depth:
            return res

    if is_win(opp):
        return NNF
    if depth == 0 or time.perf_counter() > deadline:
        return get_heuristic_bb(me, opp)

    value = NNF
    first_child = True

    for col in _ordered_moves():
        col_mask = 0b111111 << (col * 7)
        occupied = (me | opp) & col_mask
        if occupied & (1 << (col * 7 + 5)):
            continue

        new_piece = (occupied + (1 << (col * 7))) & col_mask

        if first_child:
            res = -pvs(opp, me | new_piece, depth - 1, -beta, -alpha, deadline)
            first_child = False
        else:
            res = -pvs(opp, me | new_piece, depth - 1, -alpha - 1, -alpha, deadline)
            if alpha < res < beta:
                res = -pvs(opp, me | new_piece, depth - 1, -beta, -res, deadline)

        value = max(value, res)
        alpha = max(alpha, value)
        if alpha >= beta:
            break

    # Ghi đè
    tt[state_hash] = (state, value, depth)
    return value

def agent(obs, config):
    start_time = time.perf_counter()
    deadline = start_time + MAX_THINK_TIME

    me, opp = encode(obs.board, obs.mark)

    # Load book on first use (important if the file is large).
    load_book()

    # --- OPENING BOOK LOOKUP ---
    if (me, opp) in OPENING_BOOK:
        # Nếu trạng thái có trong bộ sách chuẩn, đánh luôn không cần suy nghĩ
        return OPENING_BOOK[(me, opp)]
    
    # Check cả trường hợp bàn cờ đối xứng
    m_state = (mirror_board(me), mirror_board(opp))
    if m_state in OPENING_BOOK:
        # Lật ngược nước đi lấy từ sách
        return 6 - OPENING_BOOK[m_state]
    # ---------------------------
    
    valid_moves = [c for c in [3, 2, 4, 1, 5, 0, 6] if obs.board[c] == 0]
    if not valid_moves: return 0

    center_col = config.columns // 2
    best_move = min(valid_moves, key=lambda c: abs(c - center_col))
    reachedDepth = 0
    
    try:
        for depth in range(reachedDepth, 20, 2):
            best_score = NNF
            move_at_this_depth = best_move
            scores = [NNF] * config.columns
            moves = [best_move] + [m for m in valid_moves if m != best_move]
            
            for col in moves:
                if time.perf_counter() > deadline:
                    raise TimeoutError
                
                col_mask = 0b111111 << (col * 7)
                occupied = (me | opp) & col_mask
                new_piece = (occupied + (1 << (col * 7))) & col_mask
                
                if is_win(me | new_piece):
                    return col
                
                if col == moves[0]:
                    score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline)
                else:
                    if best_score == NNF:
                        score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline)
                    else:
                        score = -pvs(opp, me | new_piece, depth, -best_score - 1, -best_score, deadline)
                        if best_score < score < INF:
                            score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline)

                # if (col == 2 or col == 4):
                #     score += 1
                # elif (col == 3):
                #     score += 2
                scores[col] = score
                if score > best_score:
                    best_score = score
                    move_at_this_depth = col
                    
            best_move = move_at_this_depth
            print("At depth:", depth, "Best move:", best_move, scores)
            reachedDepth = depth
            if best_score == INF:
                break
            
    except TimeoutError:
        pass
        
    think_time = time.perf_counter() - start_time
    print("Principal agent reached depth", reachedDepth)
    try:
        log_system.log_move("BitboardAgent", int(best_move), think_time)
    except Exception:
        pass

    return int(best_move)
