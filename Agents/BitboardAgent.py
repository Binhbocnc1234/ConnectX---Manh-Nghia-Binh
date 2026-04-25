# DA CAP NHAT BITBOARD - VUI LONG RELOAD FILE
import random
import time
import numpy as np
import log_system
from foundation import *
import log_system
# Cấu hình
TIME_LIMIT = 1.0

class BitboardAgent:
    def __init__(self, config):
        self.rows = config.rows
        self.cols = config.columns
        self.inarow = config.inarow
        self.tt = {} # Transposition Table

    def encode(self, board, mark):
        """Chuyển matrix 1D sang 2 bitboards."""
        me = 0
        opp = 0
        for c in range(self.cols):
            for r in range(self.rows):
                val = board[r * self.cols + c]
                if val == 0: continue
                # Layout: Cột 0 là bit 0-6, Cột 1 là 7-13...
                bit = 1 << (c * 7 + (self.rows - 1 - r))
                if val == mark: me |= bit
                else: opp |= bit
        return me, opp

    def is_win(self, b):
        """Kiểm tra thắng cờ bằng phép toán bit."""
        # Ngang
        m = b & (b << 7)
        if m & (m << 14): return True
        # Dọc
        m = b & (b << 1)
        if m & (m << 2): return True
        # Chéo /
        m = b & (b << 8)
        if m & (m << 16): return True
        # Chéo \
        m = b & (b << 6)
        if m & (m << 12): return True
        return False

    def get_heuristic(self, me, opp):
        """Đánh giá nhanh thế trận."""
        if self.is_win(me): return 1000000
        if self.is_win(opp): return -1000000
        
        # Điểm cộng cho quân ở cột trung tâm
        center_mask = 0b111111 << (3 * 7)
        score = bin(me & center_mask).count('1') * 20
        score -= bin(opp & center_mask).count('1') * 20
        
        # Điểm cộng cho các chuỗi tiềm năng
        # (Ở mức độ bitboard, ta có thể thêm nhiều pattern hơn)
        return score

    def negamax(self, me, opp, depth, alpha, beta, deadline):
        state = (me, opp)
        if state in self.tt:
            res, d = self.tt[state]
            if d >= depth: return res

        if self.is_win(opp): return -1000000 - depth
        if depth == 0 or time.perf_counter() > deadline:
            return self.get_heuristic(me, opp)

        value = -1000001
        # Thứ tự thử các cột: ưu tiên trung tâm
        for col in [3, 2, 4, 1, 5, 0, 6]:
            col_mask = 0b111111 << (col * 7)
            occupied = (me | opp) & col_mask
            if occupied & (1 << (col * 7 + 5)): continue # Cột đầy
            
            new_piece = (occupied + (1 << (col * 7))) & col_mask
            res = -self.negamax(opp, me | new_piece, depth - 1, -beta, -alpha, deadline)
            
            value = max(value, res)
            alpha = max(alpha, value)
            if alpha >= beta: break
            
        self.tt[state] = (value, depth)
        return value

def agent(obs, config):
    start_time = time.perf_counter()
    deadline = start_time + TIME_LIMIT
    
    bot = BitboardAgent(config)
    me, opp = bot.encode(obs.board, obs.mark)
    
    # Lấy danh sách nước đi hợp lệ
    valid_moves = [c for c in [3, 2, 4, 1, 5, 0, 6] if obs.board[c] == 0]
    if not valid_moves: return 0
    
    best_move = valid_moves[0]
    
    # Tìm kiếm sâu dần (Iterative Deepening)
    try:
        for depth in range(1, 20):
            best_score = -2000000
            move_at_this_depth = best_move
            
            # Ưu tiên thử nước tốt nhất từ độ sâu trước đó
            moves = [best_move] + [m for m in valid_moves if m != best_move]
            
            for col in moves:
                if time.perf_counter() > deadline - 0.05: raise TimeoutError
                
                col_mask = 0b111111 << (col * 7)
                occupied = (me | opp) & col_mask
                new_piece = (occupied + (1 << (col * 7))) & col_mask
                
                if bot.is_win(me | new_piece): return col # Thắng luôn
                
                score = -bot.negamax(opp, me | new_piece, depth, -2000000, 2000000, deadline)
                if score > best_score:
                    best_score = score
                    move_at_this_depth = col
                    
            best_move = move_at_this_depth
            if best_score > 900000: break
            
    except TimeoutError:
        pass
        
    think_time = time.perf_counter() - start_time
    try:
        log_system.log_move("BitboardAgent", int(best_move), think_time)
    except Exception:
        pass

    return int(best_move)