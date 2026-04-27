# ============================================================================
# HEURISTIC EVALUATION LAYER - Đánh giá trạng thái board
# ============================================================================
from Agents.foundation import *

_BB_WINDOW_MASKS_CACHE = {}

# Buff nhỏ để ưu tiên thế trận tốt, không đủ lớn để lấn át nguy cơ thắng/thua.
BB_CENTER_BONUS = 2
BB_FILL_BONUS = 1
BB_BONUS_CAP = 12

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
        score -= (2**((2*i)+1))*num_opp[i+1]
    return score


def count_windows(grid, piece, config):
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


def get_heuristic_bb(me, opp):
    # Thắng/thua luôn là ưu tiên tuyệt đối.
    num = count_windows_bb(me, opp)
    for i in range(config.inarow):
        if i == (config.inarow - 1) and num[i + 1] >= 1:
            return float("inf") #thắng
    num_opp = count_windows_bb(opp, me)
    for i in range(config.inarow):
        if i == (config.inarow - 1) and num_opp[i + 1] >= 1:
            return float("-inf") #thua

    score = 0
    # Điểm chính: giống logic của get_heuristic(), dùng cửa sổ tiềm năng để đánh giá.
    for i in range(config.inarow):
        score += (4 ** i) * num[i + 1]
    for i in range(config.inarow):
        score -= (2 ** ((2 * i) + 1)) * num_opp[i + 1]
    return score


def _get_bb_window_masks():
    key = (config.rows, config.columns, config.inarow)
    if key in _BB_WINDOW_MASKS_CACHE:
        return _BB_WINDOW_MASKS_CACHE[key]

    masks = []

    # horizontal
    for row in range(config.rows):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + row)
            masks.append(mask)

    # vertical
    for row in range(config.rows - (config.inarow - 1)):
        for col in range(config.columns):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << (col * 7 + (row + k))
            masks.append(mask)

    # positive diagonal
    for row in range(config.rows - (config.inarow - 1)):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + (row + k))
            masks.append(mask)

    # negative diagonal
    for row in range(config.inarow - 1, config.rows):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + (row - k))
            masks.append(mask)

    _BB_WINDOW_MASKS_CACHE[key] = masks
    return masks


def count_windows_bb(me, opp):
    num_windows = np.zeros(config.inarow + 1)
    for mask in _get_bb_window_masks():
        if (mask & opp) != 0:
            continue
        num_windows[(mask & me).bit_count()] += 1
    return num_windows


