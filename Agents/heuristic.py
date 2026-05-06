# ============================================================================
# HEURISTIC EVALUATION LAYER - Đánh giá trạng thái board
# ============================================================================
from Agents.foundation import *

_BB_WINDOW_MASKS_CACHE = {}


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
            return INF
        score += (4**(i))*num[i+1]
    num_opp = count_windows (grid,mark%2+1,config)
    for i in range(config.inarow):
        if (i==(config.inarow-1) and num_opp[i+1] >= 1):
            return float ("-inf")
        score -= (2**((2*i)+1))*num_opp[i+1]
    return score


def count_windows(grid, piece, config):
    num_windows = [0] * (config.inarow + 1)
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


def get_heuristic_bb(me, opp, remaining_depth = 0):
    """
    Heuristic cho bitboard.

    Cách đọc:
    - `me` là bitboard của người chơi hiện tại.
    - `opp` là bitboard của đối thủ.
    - Hàm này mô phỏng tinh thần của `get_heuristic()`:
      + thắng/thua là ưu tiên tuyệt đối
      + sau đó mới cộng/trừ điểm theo số window tiềm năng

    Ý tưởng chính:
    - Nếu `me` đã có 4-in-a-row thì trả về `inf` ngay.
    - Nếu `opp` đã có 4-in-a-row thì trả về `-inf` ngay.
    - Nếu chưa có ván thắng/thua, chấm điểm theo các window:
      + window càng nhiều quân của mình thì càng tốt
      + window càng nhiều quân của đối thủ thì càng xấu
    """

    # Kiểm tra nguy cơ thua ngay từ góc nhìn của đối thủ.
    num_opp = count_windows_bb(opp, me)
    for i in range(config.inarow):
        if i == (config.inarow - 1) and num_opp[i + 1] >= 1:
            return NNF - remaining_depth # thua ngay
        
    # Thắng/thua luôn là ưu tiên tuyệt đối, không để các điểm phụ lấn át.
    num = count_windows_bb(me, opp)
    for i in range(config.inarow):
        if i == (config.inarow - 1) and num[i + 1] >= 1:
            return INF + remaining_depth  # thắng ngay

    score = 0
    # Phần điểm chính: giống `get_heuristic()`.
    # num[i + 1] = số window có đúng (i + 1) quân của mình.
    for i in range(config.inarow):
        score += (4 ** i) * num[i + 1]
    # Trừ điểm cho window tiềm năng của đối thủ.
    for i in range(config.inarow):
        score -= (4 ** i) * num_opp[i + 1]
    return score


def _get_bb_window_masks():
    """
    Sinh toàn bộ mask của các window 4 ô trên board bitboard.

    Vì connectX ở đây luôn là board cố định 6x7, số window hợp lệ là cố định.
    Do đó hàm này:
    - tạo mask một lần
    - lưu vào cache `_BB_WINDOW_MASKS_CACHE`
    - các lần gọi sau chỉ lấy lại từ cache để tiết kiệm thời gian

    Mỗi mask là một window 4 ô theo một trong 4 hướng:
    - ngang
    - dọc
    - chéo xuôi
    - chéo ngược

    `count_windows_bb()` sẽ dùng các mask này để đếm:
    - window nào chỉ có quân của `me`
    - window nào có quân của đối thủ thì bỏ qua
    """

    # Dùng tuple (rows, columns, inarow) làm key để cache mask theo cấu hình.
    key = (config.rows, config.columns, config.inarow)
    if key in _BB_WINDOW_MASKS_CACHE:
        return _BB_WINDOW_MASKS_CACHE[key]

    masks = []

    # Window ngang: cùng một hàng, tăng dần theo cột.
    for row in range(config.rows):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + row)
            masks.append(mask)

    # Window dọc: cùng một cột, tăng dần theo hàng.
    for row in range(config.rows - (config.inarow - 1)):
        for col in range(config.columns):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << (col * 7 + (row + k))
            masks.append(mask)

    # Chéo xuôi: đi từ trái-trên xuống phải-dưới.
    for row in range(config.rows - (config.inarow - 1)):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + (row + k))
            masks.append(mask)

    # Chéo ngược: đi từ trái-dưới lên phải-trên.
    for row in range(config.inarow - 1, config.rows):
        for col in range(config.columns - (config.inarow - 1)):
            mask = 0
            for k in range(config.inarow):
                mask |= 1 << ((col + k) * 7 + (row - k))
            masks.append(mask)

    # Lưu cache để các lần sau không phải tạo lại toàn bộ mask.
    _BB_WINDOW_MASKS_CACHE[key] = masks
    return masks


def count_windows_bb(me, opp):
    num_windows = [0] * (config.inarow + 1)
    for mask in _get_bb_window_masks():
        if (mask & opp) != 0:
            continue
        num_windows[(mask & me).bit_count()] += 1
    return num_windows


