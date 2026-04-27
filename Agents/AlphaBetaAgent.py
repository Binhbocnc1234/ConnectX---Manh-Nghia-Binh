import random
import time
import numpy as np
from Agents.foundation import *
from Agents.heuristic import *
import log_system


class SearchTimeout(Exception):
    """Raised when minimax search exceeds the global time budget."""


# MAX_THINK_TIME = 1.85
SEARCH_DEADLINE = float("inf")


def _check_timeout():
    if time.perf_counter() >= SEARCH_DEADLINE:
        raise SearchTimeout()
def is_timeout():
    return time.perf_counter() >= SEARCH_DEADLINE

def _ordered_moves(valid_moves, config):
    """Ưu tiên cột gần trung tâm để tăng hiệu quả alpha-beta pruning."""
    center_col = config.columns // 2
    return sorted(valid_moves, key=lambda c: abs(c - center_col))

# ============================================================================
# CẤU TRÚC CODE
# ============================================================================
# Layer 1 (Foundation - foundation.py):
#   └─ drop_piece()    - Thả quân
#   └─ check_window()  - Kiểm tra window
#
# Layer 2 (Heuristic - file này):
#   └─ count_windows() - Đếm windows (dùng check_window)
#   └─ get_heuristic() - Tính điểm board (dùng count_windows)
#
# Layer 3 (Minimax - file này):
#   └─ score_move_a() - Tính điểm lượt bạn (dùng drop_piece, get_heuristic, score_move_b)
#   └─ score_move_b() - Tính điểm lượt đối thủ (dùng drop_piece, get_heuristic, score_move_a)
#   └─ agent()        - Chọn nước đi tốt nhất (dùng score_move_a)
# ============================================================================

# ============================================================================
# MINIMAX DECISION TREE LAYER - Quyết định nước đi tối ưu
# ============================================================================

def score_move_a(grid, col, mark, config, n_steps=1, alpha=float("-inf"), beta=float("inf")):
    """
    Minimax Layer: Tính điểm khi ĐẾN LƯỢT BẠN.
    
    Ý nghĩa:
    - Bạn thả quân vào cột col
    - Nếu game kết thúc (board đầy hoặc hết bước), đánh giá heuristic
    - Còn nước đi: gọi score_move_b() cho tất cả cột của đối thủ, lấy MIN (đối thủ chơi tối ưu)
    
    Phụ thuộc: drop_piece(), get_heuristic(), score_move_b()
    Được gọi bởi: score_move_b() (đệ quy), agent()
    Độ phức tạp:
    - Minimax thường: O(b^d)
    - Alpha-beta (best case): O(b^(d/2))
    Tham số:
    - n_steps: Độ sâu tìm kiếm (lookahead)
    """

    next_grid = drop_piece(grid, col, mark)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    score = get_heuristic(next_grid, mark, config)
    _check_timeout()
    #Since we have just dropped our piece there is only the possibility of us getting 4 in a row and not the opponent.
    #Thus score can only be +infinity.
    if len(valid_moves)==0 or n_steps ==0 or score == float("inf"):
        return score
    else:
        value = float("inf")
        ordered_moves = _ordered_moves(valid_moves, config)
        for next_col in ordered_moves:
            child_score = score_move_b(next_grid, next_col, mark, config, n_steps-1, alpha, beta)
            value = min(value, child_score)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

def score_move_b(grid, col, mark, config, n_steps, alpha=float("-inf"), beta=float("inf")):
    """
    Minimax Layer: Tính điểm khi ĐẾN LƯỢT ĐỐI THỦ.
    """
    next_grid = drop_piece(grid,col,(mark%2)+1)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    score = get_heuristic(next_grid, mark, config)
    _check_timeout()
    #The converse is true here.
    #Since we have just dropped opponent piece there is only the possibility of opponent getting 4 in a row and not us.
    #Thus score can only be -infinity.
    if len(valid_moves)==0 or n_steps ==0 or score == float ("-inf"):
        return score
    else:
        value = float("-inf")
        ordered_moves = _ordered_moves(valid_moves, config)
        for next_col in ordered_moves:
            child_score = score_move_a(next_grid, next_col, mark, config, n_steps-1, alpha, beta)
            value = max(value, child_score)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

def agent(obs, config):
    """
    HÀM CHÍNH: Chọn nước đi tốt nhất cho AI.
    
    Ý nghĩa:
    - Kiếm tất cả nước đi hợp lệ
    - Dùng minimax để tính điểm cho mỗi nước đi
    - Chọn nước đi có điểm cao nhất (random nếu có nhiều)
    
    Phụ thuộc: score_move_a()
    Được gọi bởi: Kaggle environment
    
    Input:
    - obs: observation (board, mark của bạn)
    - config: cấu hình game (rows = 6, columns = 7, inarow = 4)
    
    Output: Cột (0 đến columns-1) để thả quân
    """
    global SEARCH_DEADLINE
    start_time = time.perf_counter()
    SEARCH_DEADLINE = start_time + MAX_THINK_TIME

    valid_moves = [c for c in range(config.columns) if obs.board[c] == 0]
    if not valid_moves:
        return 0

    center_col = config.columns // 2
    best_move = min(valid_moves, key=lambda c: abs(c - center_col))
    last_completed_depth = 0

    grid = np.asarray(obs.board).reshape(config.rows, config.columns)
    try:
        for depth in range(1, 20):
            depth_best_score = float("-inf")
            depth_best_move = best_move
            alpha = float("-inf")
            beta = float("inf")
            for col in _ordered_moves(valid_moves, config):
                _check_timeout()
                score = score_move_a(grid, col, obs.mark, config, depth, alpha, beta)
                if score > depth_best_score:
                    depth_best_score = score
                    depth_best_move = col
                alpha = max(alpha, depth_best_score)

            best_move = depth_best_move
            last_completed_depth = depth
    except SearchTimeout:
        # Return best move found so far when time budget is exhausted.
        pass
    
    # Track think time
    print("Reached Depth:", last_completed_depth)
    think_time = time.perf_counter() - start_time
    log_system.log_move("AlphaBetaAgent", best_move, think_time)
    
    return best_move
