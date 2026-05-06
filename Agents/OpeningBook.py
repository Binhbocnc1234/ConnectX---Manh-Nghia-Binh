import time
import log_system
from Agents.foundation import *
from Agents.heuristic import get_heuristic_bb

# https://grokipedia.com/page/Principal_variation_search
def _ordered_moves():
    """Ưu tiên cột gần trung tâm"""
    return [3, 2, 4, 1, 5, 0, 6]

MOVE_ORDER = _ordered_moves()


def mirror_board(bb):
    """Lật bitboard qua trục dọc (đối xứng trái-phải)."""
    m = 0
    m |= (bb & 0x7F) << 42          # Col 0 -> 6
    m |= (bb & (0x7F << 7)) << 28   # Col 1 -> 5
    m |= (bb & (0x7F << 14)) << 14  # Col 2 -> 4
    m |= (bb & (0x7F << 21))        # Col 3 -> 3
    m |= (bb & (0x7F << 28)) >> 14  # Col 4 -> 2
    m |= (bb & (0x7F << 35)) >> 28  # Col 5 -> 1
    m |= (bb & (0x7F << 42)) >> 42  # Col 6 -> 0
    return m


# -------------------------
# Transposition Table (TT)
# Zobrist + bucket + bound type + bestMove
# -------------------------

TT_BUCKETS = 1 << 23  # số bucket (power-of-two để dùng bitmask)
TT_BUCKET_MASK = TT_BUCKETS - 1
TT_BUCKET_SIZE = 4

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

# dict[int bucketIndex] -> list[tuple(key64, depth, value, flag, bestMove)]
tt = {}


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF


def _make_zobrist_tables(seed: int = 0xC0FFEE):
    # 49 bits/column representation (7*7) but we only ever use 6 bits per column.
    z_me = [0] * 49
    z_opp = [0] * 49
    x = seed & 0xFFFFFFFFFFFFFFFF
    for i in range(49):
        x = _splitmix64(x)
        z_me[i] = x
        x = _splitmix64(x)
        z_opp[i] = x
    return z_me, z_opp


_Z_ME, _Z_OPP = _make_zobrist_tables()


def zobrist_hash(me: int, opp: int) -> int:
    """Deterministic 64-bit Zobrist hash for (me, opp) bitboards."""
    h = 0
    bb = me
    while bb:
        lsb = bb & -bb
        idx = lsb.bit_length() - 1
        h ^= _Z_ME[idx]
        bb ^= lsb
    bb = opp
    while bb:
        lsb = bb & -bb
        idx = lsb.bit_length() - 1
        h ^= _Z_OPP[idx]
        bb ^= lsb
    return h & 0xFFFFFFFFFFFFFFFF


def _canonical_tt_key(me: int, opp: int):
    """Return (key64, flip) where flip=True means mirrored orientation chosen."""
    key = zobrist_hash(me, opp)
    m_me = mirror_board(me)
    m_opp = mirror_board(opp)
    m_key = zobrist_hash(m_me, m_opp)
    if (m_key < key) or (m_key == key and (m_me, m_opp) < (me, opp)):
        return m_key, True
    return key, False


def _tt_probe(key64: int, depth: int, alpha: float, beta: float):
    """Probe TT.

    Returns (hit_value_or_None, new_alpha, new_beta, bestMoveHint).
    bestMoveHint can be used for move ordering even when no cutoff/EXACT hit.
    """
    idx = key64 & TT_BUCKET_MASK
    bucket = tt.get(idx)
    if not bucket:
        return None, alpha, beta, -1

    best_hint = -1
    best_hint_depth = -1

    for k, d, v, flag, bm in bucket:
        if k != key64:
            continue
        if bm != -1 and d > best_hint_depth:
            best_hint = bm
            best_hint_depth = d
        if d < depth:
            continue

        if flag == TT_EXACT:
            return v, alpha, beta, bm
        if flag == TT_LOWER:
            if v > alpha:
                alpha = v
        elif flag == TT_UPPER:
            if v < beta:
                beta = v
        if alpha >= beta:
            return v, alpha, beta, bm

    return None, alpha, beta, best_hint


def _tt_store(key64: int, depth: int, value: float, flag: int, best_move: int):
    idx = key64 & TT_BUCKET_MASK
    bucket = tt.get(idx)
    entry = (key64, depth, value, flag, best_move)
    if bucket is None:
        tt[idx] = [entry]
        return

    # Replace same key if deeper/equal.
    for i, (k, d, _, _, _) in enumerate(bucket):
        if k == key64:
            if depth >= d:
                bucket[i] = entry
            return

    if len(bucket) < TT_BUCKET_SIZE:
        bucket.append(entry)
        return

    # Bucket full: replace the shallowest entry.
    victim_i = 0
    victim_depth = bucket[0][1]
    for i in range(1, len(bucket)):
        d = bucket[i][1]
        if d < victim_depth:
            victim_depth = d
            victim_i = i
    bucket[victim_i] = entry


import os
import json

# -------------------------
# Static Opening Book
# -------------------------
OPENING_BOOK = None

def load_opening_book():
    global OPENING_BOOK
    if OPENING_BOOK is not None:
        return
    OPENING_BOOK = {}
    
    # Locate opening_book.jsonl in the same directory as this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    book_path = os.path.join(current_dir, "opening_book.jsonl")
    
    if os.path.exists(book_path):
        count = 0
        try:
            with open(book_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    me_book, opp_book, move = data["me"], data["opp"], data["move"]
                    key64, flip = _canonical_tt_key(me_book, opp_book)
                    
                    # Cần lưu lại nước đi đối với trạng thái canonical. 
                    # Nếu trạng thái (me_book, opp_book) bị lật để thành canonical, thì nước đi cũng phải lật.
                    canonical_move = 6 - move if flip else move
                    OPENING_BOOK[key64] = canonical_move
                    count += 1
            print(f"[Opening Book] Loaded {count} canonical positions from {book_path}.")
        except Exception as e:
            print(f"[Opening Book] Error loading book: {e}")
    else:
        print(f"[Opening Book] Warning: {book_path} not found. Proceeding without book.")


searching_depth = 0
def pvs(me, opp, depth, alpha, beta, deadline):
    if is_win(opp):
        return NNF
    if depth == 0 or time.perf_counter() > deadline:
        return get_heuristic_bb(me, opp)

    alpha0, beta0 = alpha, beta

    key64, flip = _canonical_tt_key(me, opp)
    tt_value, alpha, beta, tt_best = _tt_probe(key64, depth, alpha, beta)
    if tt_value is not None:
        return tt_value

    # bestMove từ TT (nếu lưu theo orientation canonical thì cần mirror lại).
    if tt_best != -1 and flip:
        tt_best = 6 - tt_best

    value = NNF
    best_move = -1
    first_child = True

    # Move ordering: TT best move (nếu hợp lệ) -> center-first order.
    ordered = []
    if tt_best != -1:
        ordered.append(tt_best)
    for c in MOVE_ORDER:
        if c != tt_best:
            ordered.append(c)

    for col in ordered:
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

        if res > value:
            value = res
            best_move = col
        alpha = max(alpha, value)
        if alpha >= beta:
            break

    # Store to TT with bound type + bestMove.
    if best_move != -1:
        store_move = 6 - best_move if flip else best_move
    else:
        store_move = -1

    if value <= alpha0:
        flag = TT_UPPER
    elif value >= beta0:
        flag = TT_LOWER
    else:
        flag = TT_EXACT

    _tt_store(key64, depth, value, flag, store_move)
    return value

def agent(obs, config):
    global searching_depth
    start_time = time.perf_counter()
    
    # 1. Determine thinking time budget
    # First move (step 0 or 1) has a budget of 55 seconds (leaving a 5s safety margin)
    is_first_turn = (obs.step == 0 or obs.step == 1)
    if is_first_turn:
        think_time_budget = 5
        print(f"[Agent] First turn detected (step {obs.step}). Allocating {think_time_budget}s to deeply search and populate TT.")
    else:
        think_time_budget = MAX_THINK_TIME
        
    deadline = start_time + think_time_budget

    me, opp = encode(obs.board, obs.mark)
    
    # Nạp Opening Book nếu chưa nạp
    load_opening_book()
    
    # 2. Query Opening Book (Fast Path)
    key64, flip = _canonical_tt_key(me, opp)
    if key64 in OPENING_BOOK:
        best_move = OPENING_BOOK[key64]
        if flip:
            best_move = 6 - best_move
        print(f"[Opening Book Hit] Playing precomputed move: {best_move}")
        
        think_time = time.perf_counter() - start_time
        try:
            log_system.log_move("OpeningBookAgent", int(best_move), think_time)
        except Exception:
            pass
        return int(best_move)
        
    # 3. Query TT directly (even if not in OPENING_BOOK, may be precomputed in TT from turn 1)
    idx = key64 & TT_BUCKET_MASK
    bucket = tt.get(idx)
    if bucket:
        best_bm = -1
        best_d = -1
        for k, d, v, flag, bm in bucket:
            if k == key64 and bm != -1 and d > best_d:
                best_bm = bm
                best_d = d
        if best_bm != -1:
            best_move = 6 - best_bm if flip else best_bm
            print(f"[TT Hit] Playing precomputed move: {best_move} (resolved from Turn 1 computation)")
            
            think_time = time.perf_counter() - start_time
            try:
                log_system.log_move("OpeningBookAgent", int(best_move), think_time)
            except Exception:
                pass
            return int(best_move)

    valid_moves = [c for c in [3, 2, 4, 1, 5, 0, 6] if obs.board[c] == 0]
    if not valid_moves: return 0
    
    center_col = config.columns // 2
    best_move = min(valid_moves, key=lambda c: abs(c - center_col))
    reachedDepth = 2
    
    # First turn search goes much deeper to seed the entire early-game TT tree
    max_search_depth = 24 if is_first_turn else 20
    
    try:
        for depth in range(reachedDepth - 2, max_search_depth, 2):
            searching_depth = depth
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
        
    # 4. (Đã xóa) Book động không còn được build sau khi search nữa vì dùng book tĩnh.
        
    think_time = time.perf_counter() - start_time
    print("[OpeningBook] reached depth", reachedDepth)
    try:
        log_system.log_move("OpeningBookAgent", int(best_move), think_time)
    except Exception:
        pass
    return int(best_move)
