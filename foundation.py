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


def check_window(window, piece, config):
    if window.count((piece%2)+1)==0:
        return window.count(piece)
    else:
        return -1