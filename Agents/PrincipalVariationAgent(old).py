import time
import log_system
from Agents.foundation import *
from Agents.heuristic import get_heuristic_bb

# https://grokipedia.com/page/Principal_variation_search
def _ordered_moves():
    """Uu tiên cột gần trung tâm"""
    return [3, 2, 4, 1, 5, 0, 6]

tt = {}  # Transposition Table
MAX_TT_SIZE = 2 ** 21  # 2^20 slots

def pvs(me, opp, depth, alpha, beta, deadline):

    # Trong ConnectX, một trạng thái bàn cờ và hình ảnh phản chiếu của nó qua trục dọc là tương đương về mặt chiến thuật.
    def mirror(bb):
        m = 0
        m |= (bb & 0x7F) << 42          # Col 0 -> 6
        m |= (bb & (0x7F << 7)) << 28   # Col 1 -> 5
        m |= (bb & (0x7F << 14)) << 14  # Col 2 -> 4
        m |= (bb & (0x7F << 21))        # Col 3 -> 3
        m |= (bb & (0x7F << 28)) >> 14  # Col 4 -> 2
        m |= (bb & (0x7F << 35)) >> 28  # Col 5 -> 1
        m |= (bb & (0x7F << 42)) >> 42  # Col 6 -> 0
        return m

    # Kiểm tra xem dữ liệu về state có ở trong table không
            
    m_state = (mirror(me), mirror(opp))
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

    return value

def agent(obs, config):
    start_time = time.perf_counter()
    deadline = start_time + MAX_THINK_TIME

    me, opp = encode(obs.board, obs.mark)
    
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
        log_system.log_move("PrincipalVariationAgent", int(best_move), think_time)
    except Exception:
        pass

    return int(best_move)
