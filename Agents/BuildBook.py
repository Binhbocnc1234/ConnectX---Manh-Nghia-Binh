import os
import sys
import json
import time

# Ensure we can import from the parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from Agents.OpeningBook import _canonical_tt_key, pvs, MOVE_ORDER
from Agents.foundation import is_win, NNF, INF
from Agents.heuristic import get_heuristic_bb

MIN_EMPTY_SPACES = 23
HEURISTIC_LIMIT = 40
SEARCH_DEPTH = 16
DEADLINE_PER_MOVE = 5.0  # seconds

def search_best_move(me, opp):
    valid_moves = [c for c in MOVE_ORDER if ( (me | opp) & (1 << (c * 7 + 5)) ) == 0]
    if not valid_moves:
        return 0
        
    best_move = valid_moves[0]
    best_score_overall = NNF
    deadline = time.perf_counter() + DEADLINE_PER_MOVE
    
    try:
        for depth in range(0, SEARCH_DEPTH, 2):
            best_score = NNF
            move_at_this_depth = best_move
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
                            
                if score > best_score:
                    best_score = score
                    move_at_this_depth = col
                    
            best_move = move_at_this_depth
            best_score_overall = best_score
            if best_score == INF:
                break
    except TimeoutError:
        pass
        
    return best_move

def build_book():
    book_path = os.path.join(current_dir, "opening_book.jsonl")
    
    queue = [(0, 0, 0)] # me, opp, ply
    visited = set()
    count = 0
    
    print(f"Bat dau xay dung Opening Book...")
    print(f"Dieu kien dung: So o trong <= {MIN_EMPTY_SPACES} hoac Heuristic > {HEURISTIC_LIMIT} (tu ply 14)")
    print(f"SEARCH_DEPTH={SEARCH_DEPTH}")
    print(f"File se duoc luu tai: {book_path}")
    
    with open(book_path, "w", encoding="utf-8") as f:
        while queue:
            me, opp, ply = queue.pop(0)
            
            # 1. Dừng nhánh nếu bàn cờ chỉ còn <= MIN_EMPTY_SPACES ô trống
            empty_spaces = 42 - ply
            if empty_spaces <= MIN_EMPTY_SPACES:
                continue
                
            # 2. Dừng nhánh nếu thế cờ quá lệch (chỉ check khi ply >= 14 để tiết kiệm time)
            if ply >= 14:
                score = get_heuristic_bb(me, opp)
                if abs(score) > HEURISTIC_LIMIT:
                    continue
                    
            key64, flip = _canonical_tt_key(me, opp)
            if key64 in visited:
                continue
            visited.add(key64)
            
            best_move = search_best_move(me, opp)
            
            record = {"me": me, "opp": opp, "move": best_move}
            f.write(json.dumps(record) + "\n")
            f.flush()
            
            count += 1
            if count % 10 == 0:
                print(f"Da xu ly {count} trang thai (dang o ply {ply})...")
                
            # Tạo các trạng thái con cho lượt tiếp theo
            # Ở trạng thái mới, người đến lượt đi là `opp`, người chờ là `me | new_piece`
            for col in MOVE_ORDER:
                col_mask = 0b111111 << (col * 7)
                occupied = (me | opp) & col_mask
                if occupied & (1 << (col * 7 + 5)):
                    continue
                    
                new_piece = (occupied + (1 << (col * 7))) & col_mask
                
                if is_win(me | new_piece):
                    continue
                
                queue.append((opp, me | new_piece, ply + 1))
                
    print(f"Hoan thanh! Da luu {count} trang thai canonical vao {book_path}")

if __name__ == "__main__":
    build_book()
