import random
import numpy as np
from foundation import *

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
    for i in range(config.inarow):
        num  = count_windows (grid,i+1,mark,config)
        score += (4**(i+1))*num
    for i in range(config.inarow):
        num_opp = count_windows (grid,i+1,mark%2+1,config)
        score-= (2**((2*i)+3))*num_opp
    return score

def count_windows(grid, num_discs, piece, config):
    """
    Đếm số lượng "cửa sổ" (window - 4 ô liên tiếp) chứa đúng num_discs quân của player.
    
    Ý nghĩa:
    - Tìm tất cả các cửa sổ 4x1 (ngang, dọc, chéo) trên board
    - Đếm có bao nhiêu cửa sổ chứa đúng num_discs quân của 'piece'
    - Ví dụ: num_discs=2 → đếm cửa sổ có 2 quân (2 trống)
    
    Phụ thuộc: check_window()
    Được gọi bởi: get_heuristic()
    """
    num_windows = 0
    # horizontal
    for row in range(config.rows):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[row, col:col+config.inarow])
            if check_window(window, num_discs, piece, config):
                num_windows += 1
    # vertical
    for row in range(config.rows-(config.inarow-1)):
        for col in range(config.columns):
            window = list(grid[row:row+config.inarow, col])
            if check_window(window, num_discs, piece, config):
                num_windows += 1
    # positive diagonal
    for row in range(config.rows-(config.inarow-1)):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[range(row, row+config.inarow), range(col, col+config.inarow)])
            if check_window(window, num_discs, piece, config):
                num_windows += 1
    # negative diagonal
    for row in range(config.inarow-1, config.rows):
        for col in range(config.columns-(config.inarow-1)):
            window = list(grid[range(row, row-config.inarow, -1), range(col, col+config.inarow)])
            if check_window(window, num_discs, piece, config):
                num_windows += 1
    return num_windows



# ============================================================================
# MINIMAX DECISION TREE LAYER - Quyết định nước đi tối ưu
# ============================================================================

# Tính điểm khi đến lượt bạn (maximize)
def score_move_a(grid, col, mark, config,n_steps=1):
    """
    Minimax Layer: Tính điểm khi ĐẾN LƯỢT BẠN.
    
    Ý nghĩa:
    - Bạn thả quân vào cột col
    - Nếu game kết thúc (board đầy hoặc hết bước), đánh giá heuristic
    - Còn nước đi: gọi score_move_b() cho tất cả cột của đối thủ, lấy MIN (đối thủ chơi tối ưu)
    
    Phụ thuộc: drop_piece(), get_heuristic(), score_move_b()
    Được gọi bởi: score_move_b() (đệ quy), agent()
    
    Tham số:
    - n_steps: Độ sâu tìm kiếm (lookahead)
    """
    next_grid = drop_piece(grid, col, mark, config)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    if len(valid_moves)==0 or n_steps ==0:
        score = get_heuristic(next_grid, mark, config)
        return score
    else :
        scores = [score_move_b(next_grid,col,mark,config,n_steps-1) for col in valid_moves]
        score = min(scores)
    return score

#  Tính điểm khi đến lượt đối thủ (minimize)
def score_move_b(grid, col, mark, config,n_steps):
    """
    Minimax Layer: Tính điểm khi ĐẾN LƯỢT ĐỐI THỦ.
    
    Ý nghĩa:
    - Đối thủ thả quân vào cột col
    - Nếu game kết thúc (board đầy hoặc hết bước), đánh giá heuristic
    - Còn nước đi: gọi score_move_a() cho tất cả cột của bạn, lấy MAX (bạn chọn tối ưu)
    
    Phụ thuộc: drop_piece(), get_heuristic(), score_move_a()
    Được gọi bởi: score_move_a() (đệ quy)
    
    Tham số:
    - n_steps: Độ sâu tìm kiếm (lookahead)
    """
    next_grid = drop_piece(grid,col,(mark%2)+1,config)
    valid_moves = [col for col in range (config.columns) if next_grid[0][col]==0]
    if len(valid_moves)==0 or n_steps ==0:
        score = get_heuristic(next_grid, mark, config)
        return score
    else :
        scores = [score_move_a(next_grid,col,mark,config,n_steps-1) for col in valid_moves]
        score = max(scores)
    return score

def agent(obs, config):
    """
    HÀM CHÍNH: Chọn nước đi tốt nhất cho AI.
    
    Ý nghĩa:
    - Kiếm tất cả nước đi hợp lệ
    - Dùng minimax để tính điểm cho mỗi nước đi (1 step lookahead)
    - Chọn nước đi có điểm cao nhất (random nếu có nhiều)
    
    Phụ thuộc: score_move_a()
    Được gọi bởi: Kaggle environment
    
    Input:
    - obs: observation (board, mark của bạn)
    - config: cấu hình game (rows, columns, inarow)
    
    Output: Cột (0 đến columns-1) để thả quân
    """
    valid_moves = [c for c in range(config.columns) if obs.board[c] == 0]
    grid = np.asarray(obs.board).reshape(config.rows, config.columns)
    scores = dict(zip(valid_moves, [score_move_a(grid, col, obs.mark, config,1) for col in valid_moves]))
    max_cols = [key for key in scores.keys() if scores[key] == max(scores.values())]
    return random.choice(max_cols)