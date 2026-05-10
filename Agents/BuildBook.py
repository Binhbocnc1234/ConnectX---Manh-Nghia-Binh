import sys
import os
import time
import struct
from collections import deque

# Import our optimized PVS algorithms
import Agents.foundation as foundation
from Agents.OpeningBook_optimized import (
    pvs,
    _make_move,
    is_win,
    _canonical_tt_key,
    MOVE_ORDER,
    NNF,
    INF,
    _find_threats,
    VALID_CELLS,
    BOTTOM_ROW
)

# Hardcoded config for building the book
MAX_PLY = 3          # Start with 6 for testing (Python is slow)
PRUNE_THRESHOLD = 20  # Only prune if it's a forced mate (MATE_SCORE is 100000)
SEARCH_DEPTH = 4     # How deep PVS should search at each node
FILE_OUT = "opening_book.bin"

def solve_position(me, opp, depth_limit):
    """
    Wrapper around `pvs` to evaluate all valid moves and find the best one.
    Returns (best_move, best_score).
    """
    best_move = -1
    best_score = NNF
    
    # Fast path: Immediate win
    for col in MOVE_ORDER:
        new_piece = _make_move(me, opp, col)
        if new_piece and is_win(me | new_piece):
            return col, 1000

    # Fast path: Opponent forced win block
    threat_cols = []
    for col in MOVE_ORDER:
        new_piece = _make_move(opp, me, col)
        if new_piece and is_win(opp | new_piece):
            threat_cols.append(col)
    
    if len(threat_cols) >= 2:
        # Unstoppable loss
        return threat_cols[0], -1000
    
    moves_to_search = MOVE_ORDER
    if len(threat_cols) == 1:
        # Forced block
        moves_to_search = [threat_cols[0]]
    else:
        # Safe moves filtering for normal moves
        occupied = me | opp
        playable_now = (occupied + BOTTOM_ROW) & VALID_CELLS
        opp_threats = _find_threats(opp) & ~me
        safe_moves_mask = playable_now & ~(opp_threats >> 1)
        
        if safe_moves_mask == 0:
            return -1, -1000 # No safe moves

    # Search
    for col in moves_to_search:
        col_mask = 0b111111 << (col * 7)
        occupied_col = (me | opp) & col_mask
        if occupied_col & (1 << (col * 7 + 5)):
            continue
            
        new_piece = (occupied_col + (1 << (col * 7))) & col_mask
        
        # Apply safe moves mask if not a forced block
        if len(threat_cols) == 0 and not (new_piece & safe_moves_mask):
            continue
        
        deadline = time.perf_counter() + 60.0 # 60s per move budget
        # We call pvs from opponent's perspective
        res = -pvs(opp, me | new_piece, depth_limit, -INF, -best_score if best_score != NNF else INF, deadline)
        
        if res > best_score:
            best_score = res
            best_move = col

    return best_move, best_score

def nbMoves(me, opp):
    return (me | opp).bit_count()

def main():
    print(f"--- Python ConnectX Book Builder ---")
    print(f"Max Ply: {MAX_PLY}, Prune Threshold: {PRUNE_THRESHOLD}, PVS Depth: {SEARCH_DEPTH}")
    
    with open(FILE_OUT, "wb") as f:
        f.write(b"BK01")
        
        queue = deque()
        visited = set()
        
        # Start with empty board
        queue.append((0, 0))
        
        count = 0
        head = 0
        misses = 0
        max_reached_depth = 0
        
        start_time = time.time()
        last_log_time = start_time
        
        while queue:
            me, opp = queue.popleft()
            head += 1
            
            depth = nbMoves(me, opp)
            if depth > max_reached_depth:
                max_reached_depth = depth
                
            if depth > MAX_PLY:
                continue
                
            # Use canonical key to check visited (avoid mirror duplicates)
            key64, flip = _canonical_tt_key(me, opp)
            if key64 in visited:
                continue
            visited.add(key64)
            
            # Evaluate position
            best_move, best_score = solve_position(me, opp, SEARCH_DEPTH)
            
            if best_move != -1:
                # Write to binary: uint64(me) + uint64(opp) + uint8(move)
                f.write(struct.pack("<QQB", me, opp, best_move))
                count += 1
            else:
                misses += 1
                
            # Prune if the score is definitive (forced win/loss)
            should_expand = True
            if abs(best_score) >= PRUNE_THRESHOLD:
                should_expand = False
                
            if head == 1:
                print(f"DEBUG Root: move={best_move}, score={best_score}, should_expand={should_expand}")
                
            if should_expand:
                for col in MOVE_ORDER:
                    new_piece = _make_move(me, opp, col)
                    if new_piece and not is_win(me | new_piece):
                        queue.append((opp, me | new_piece))
            
            # Logging
            if head % 100 == 0:
                now = time.time()
                if now - last_log_time >= 5.0:  # Print every 5 seconds
                    hit_rate = (count / head) * 100.0 if head > 0 else 0
                    q_size = len(queue)
                    print(f"Processed {head} pos | Hits: {count} ({hit_rate:.1f}%) | Max Depth: {max_reached_depth} | Queue: {q_size}")
                    f.flush()
                    last_log_time = now
                    
        print(f"\n--- Done ---")
        print(f"Exported {count} positions to {FILE_OUT}")
        print(f"Total time: {time.time() - start_time:.1f}s")

if __name__ == "__main__":
    main()
