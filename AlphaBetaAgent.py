import random
import time
import numpy as np
from foundation import *
import log_system


class SearchTimeout(Exception):
    """Raised when minimax search exceeds the global time budget."""


MAX_THINK_TIME = 1.6
SEARCH_DEADLINE = float("inf")


def _check_timeout():
    if time.perf_counter() >= SEARCH_DEADLINE:
        raise SearchTimeout()


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
# HEURISTIC EVALUATION LAYER - Đánh giá trạng thái board
# ============================================================================

def get_heuristic(grid, mark, config):
    """
    Tính điểm đánh giá (heuristic score) cho một trạng thái board.
    
    Ý nghĩa:
    - Cộng điểm nếu bạn có nhiều quân liên tiếp (cơ hội thắng)
    - Trừ điểm nếu đối thủ có nhiều quân liên tiếp (nguy hiểm)
    - Sử dụng cấp số nhân: 2 quân = 4^2, 3 quân = 4^3, 4 quân = 4^4
    
    Phụ thuộc: count_windows()
    """
    score = 0
    num = count_windows(grid,mark,config)
    for i in range(config.inarow):
        if (i==(config.inarow-1) and num[i+1] >= 1):
            return float("inf")
        score += (4**(i))*num[i+1]
    num_opp = count_windows (grid,mark%2+1,config)
    for i in range(config.inarow):
        if (i==(config.inarow-1) and num_opp[i+1] >= 1):
            return float ("-inf")
        score-= (2**((2*i)+1))*num_opp[i+1]
    return score


def count_windows(grid, piece, config):
    """
    Đếm số lượng "cửa sổ" (window - 4 ô liên tiếp) chứa đúng num_discs quân của player.
    
    Ý nghĩa:
    - Tìm tất cả các cửa sổ 4x1 (ngang, dọc, chéo) trên board
    - Đếm có bao nhiêu cửa sổ chứa đúng num_discs quân của 'piece'
    - Ví dụ: num_discs=2 → đếm cửa sổ có 2 quân (2 trống)
    
    Phụ thuộc: check_window()
    Được gọi bởi: get_heuristic()
    """
    num_windows = np.zeros(config.inarow+1)
    # horizontal
    for row in range(config.rows):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[row, col:col+config.inarow])
            type_window = check_window(window, piece, config)
            if type_window != -1:
                num_windows[type_window] += 1
    # vertical
    for row in range(config.rows-(config.inarow-1)):
        for col in range(config.columns):
            window = list(grid[row:row+config.inarow, col])
            type_window = check_window(window, piece, config)
            if type_window != -1:
                num_windows[type_window] += 1
    # positive diagonal
    for row in range(config.rows-(config.inarow-1)):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[range(row, row+config.inarow), range(col, col+config.inarow)])
            type_window = check_window(window, piece, config)
            if type_window != -1:
                num_windows[type_window] += 1
    # negative diagonal
    for row in range(config.inarow-1, config.rows):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[range(row, row-config.inarow, -1), range(col, col+config.inarow)])
            type_window = check_window(window, piece, config)
            if type_window != -1:
                num_windows[type_window] += 1
    return num_windows


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
    _check_timeout()
    next_grid = drop_piece(grid, col, mark, config)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    score = get_heuristic(next_grid, mark, config)
    #Since we have just dropped our piece there is only the possibility of us getting 4 in a row and not the opponent.
    #Thus score can only be +infinity.
    if len(valid_moves)==0 or n_steps ==0 or score == float("inf"):
        return score
    else:
        value = float("inf")
        ordered_moves = _ordered_moves(valid_moves, config)
        for next_col in ordered_moves:
            _check_timeout()
            child_score = score_move_b(next_grid, next_col, mark, config, n_steps-1, alpha, beta)
            value = min(value, child_score)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value
    return score

def score_move_b(grid, col, mark, config, n_steps, alpha=float("-inf"), beta=float("inf")):
    """
    Minimax Layer: Tính điểm khi ĐẾN LƯỢT ĐỐI THỦ.
    """
    _check_timeout()
    next_grid = drop_piece(grid,col,(mark%2)+1,config)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    score = get_heuristic(next_grid, mark, config)
    #The converse is true here.
    #Since we have just dropped opponent piece there is only the possibility of opponent getting 4 in a row and not us.
    #Thus score can only be -infinity.
    if len(valid_moves)==0 or n_steps ==0 or score == float ("-inf"):
        return score
    else:
        value = float("-inf")
        ordered_moves = _ordered_moves(valid_moves, config)
        for next_col in ordered_moves:
            _check_timeout()
            child_score = score_move_a(next_grid, next_col, mark, config, n_steps-1, alpha, beta)
            value = max(value, child_score)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value
    return score

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
    global SEARCH_DEADLINE, MOVE_LOG
    start_time = time.perf_counter()
    SEARCH_DEADLINE = start_time + MAX_THINK_TIME

    valid_moves = [c for c in range(config.columns) if obs.board[c] == 0]
    if not valid_moves:
        return 0

    center_col = config.columns // 2
    best_move = min(valid_moves, key=lambda c: abs(c - center_col))
    best_score = float("-inf")
    scores = {}
    alpha = float("-inf")
    beta = float("inf")

    grid = np.asarray(obs.board).reshape(config.rows, config.columns)
    try:
        for col in _ordered_moves(valid_moves, config):
            _check_timeout()
            score = score_move_a(grid, col, obs.mark, config, 4, alpha, beta)
            scores[col] = score
            if score > best_score:
                best_score = score
                best_move = col
            alpha = max(alpha, best_score)
    except SearchTimeout:
        # Return best move found so far when time budget is exhausted.
        pass

    top_cols = [col for col, score in scores.items() if score == best_score]

    if top_cols:
        best_move = random.choice(top_cols)
    
    # Track think time
    think_time = time.perf_counter() - start_time
    log_system.log_move("AlphaBetaAgent", best_move, think_time)
    
    return best_move

