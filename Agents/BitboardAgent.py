import time
import log_system
from Agents.foundation import *
from Agents.heuristic import get_heuristic_bb

def minimax(me, opp, depth, alpha, beta, deadline, tt):
    state = (me, opp)
    if state in tt:
        res, d = tt[state]
        if d >= depth:
            return res

    if is_win(opp):
        return -1000000 - depth
    if depth == 0 or time.perf_counter() > deadline:
        return get_heuristic_bb(me, opp)

    value = -1000001
    # Thứ tự thử các cột: ưu tiên trung tâm
    for col in [3, 2, 4, 1, 5, 0, 6]:
        col_mask = 0b111111 << (col * 7)
        occupied = (me | opp) & col_mask
        if occupied & (1 << (col * 7 + 5)):
            continue  # Cột đầy

        new_piece = (occupied + (1 << (col * 7))) & col_mask
        res = -minimax(opp, me | new_piece, depth - 1, -beta, -alpha, deadline, tt)

        value = max(value, res)
        alpha = max(alpha, value)
        if alpha >= beta:
            break

    tt[state] = (value, depth)
    return value

def agent(obs, config):
    start_time = time.perf_counter()
    deadline = start_time + MAX_THINK_TIME

    tt = {}  # Transposition Table
    me, opp = encode(obs.board, obs.mark)
    
    # Lấy danh sách nước đi hợp lệ
    valid_moves = [c for c in [3, 2, 4, 1, 5, 0, 6] if obs.board[c] == 0]
    if not valid_moves: return 0
    
    best_move = valid_moves[0]
    reachedDepth = 2
    # Tìm kiếm sâu dần (Iterative Deepening)
    try:
        for depth in range(reachedDepth-1, 20):
            best_score = -2000000
            move_at_this_depth = best_move
            
            # Ưu tiên thử nước tốt nhất từ độ sâu trước đó
            moves = [best_move] + [m for m in valid_moves if m != best_move]
            
            for col in moves:
                if time.perf_counter() > deadline:
                    raise TimeoutError
                
                col_mask = 0b111111 << (col * 7)
                occupied = (me | opp) & col_mask
                new_piece = (occupied + (1 << (col * 7))) & col_mask
                
                if is_win(me | new_piece):
                    return col  # Thắng luôn
                
                score = -minimax(opp, me | new_piece, depth, -2000000, 2000000, deadline, tt)
                if score > best_score:
                    best_score = score
                    move_at_this_depth = col
                    
            best_move = move_at_this_depth
            reachedDepth = depth
            if best_score > 900000: break
            
    except TimeoutError:
        pass
        
    think_time = time.perf_counter() - start_time
    print("Bitboard agent reached depth", reachedDepth)
    try:
        log_system.log_move("BitboardAgent", int(best_move), think_time)
    except Exception:
        pass

    return int(best_move)