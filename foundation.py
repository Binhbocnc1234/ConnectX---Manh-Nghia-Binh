"""
FOUNDATION LAYER - Các hàm cơ bản không phụ thuộc
================================================
Những hàm này là nền tảng, không gọi hàm khác.
Học những hàm này trước để hiểu game mechanics.
"""

import numpy as np


def drop_piece(grid, col, mark, config):
    """
    Simulate: Thả 1 quân vào cột col và trả về board mới.
    
    Ý nghĩa:
    - Tìm hàng trống thấp nhất trong cột (vật lý trò chơi)
    - Đặt quân (mark=1 hoặc 2) vào vị trí đó
    - Không thay đổi board gốc (trả về board copy)
    
    Phụ thuộc: Không gọi hàm khác
    Được gọi bởi: score_move_a(), score_move_b()
    
    Ví dụ:
    >>> grid = np.array([[0,0,0],[0,0,0],[0,0,0]])
    >>> result = drop_piece(grid, 1, 1, config)
    >>> result[2,1] == 1  # Quân rơi xuống hàng cuối
    True
    """
    next_grid = grid.copy()
    for row in range(config.rows-1, -1, -1):
        if next_grid[row][col] == 0:
            break
    next_grid[row][col] = mark
    return next_grid


def check_window(window, num_discs, piece, config):
    """
    Kiểm tra cửa sổ có hợp lệ không.
    
    Ý nghĩa:
    - Trả về True nếu cửa sổ chứa đúng num_discs quân 'piece' và phần còn lại trống (0)
    - Ví dụ: window=[1,1,0,0], num_discs=2, piece=1 → True
    
    Phụ thuộc: Không gọi hàm khác
    Được gọi bởi: count_windows()
    
    Ví dụ:
    >>> window = [1, 1, 0, 0]
    >>> check_window(window, 2, 1, config)  # 2 quân 1, 2 trống
    True
    >>> check_window(window, 1, 1, config)  # 1 quân 1, 3 trống (sai)
    False
    """
    return (window.count(piece) == num_discs and window.count(0) == config.inarow-num_discs)
