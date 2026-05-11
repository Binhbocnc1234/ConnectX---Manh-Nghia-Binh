#include "core.ipp"

namespace {

std::vector<std::uint64_t> bb_window_masks;
bool bb_window_masks_ready = false;

void ensure_bb_window_masks() {
    if (bb_window_masks_ready) return;

    bb_window_masks.clear();

    for (int row = 0; row < ROWS; ++row) {
        for (int col = 0; col < COLUMNS - (INAROW - 1); ++col) {
            std::uint64_t mask = 0;
            for (int k = 0; k < INAROW; ++k) {
                mask |= 1ULL << ((col + k) * 7 + row);
            }
            bb_window_masks.push_back(mask);
        }
    }

    for (int row = 0; row < ROWS - (INAROW - 1); ++row) {
        for (int col = 0; col < COLUMNS; ++col) {
            std::uint64_t mask = 0;
            for (int k = 0; k < INAROW; ++k) {
                mask |= 1ULL << (col * 7 + (row + k));
            }
            bb_window_masks.push_back(mask);
        }
    }

    for (int row = 0; row < ROWS - (INAROW - 1); ++row) {
        for (int col = 0; col < COLUMNS - (INAROW - 1); ++col) {
            std::uint64_t mask = 0;
            for (int k = 0; k < INAROW; ++k) {
                mask |= 1ULL << ((col + k) * 7 + (row + k));
            }
            bb_window_masks.push_back(mask);
        }
    }

    for (int row = INAROW - 1; row < ROWS; ++row) {
        for (int col = 0; col < COLUMNS - (INAROW - 1); ++col) {
            std::uint64_t mask = 0;
            for (int k = 0; k < INAROW; ++k) {
                mask |= 1ULL << ((col + k) * 7 + (row - k));
            }
            bb_window_masks.push_back(mask);
        }
    }

    bb_window_masks_ready = true;
}

std::array<int, INAROW + 1> count_windows_bb(std::uint64_t me, std::uint64_t opp) {
    ensure_bb_window_masks();
    std::array<int, INAROW + 1> num_windows{};
    for (std::uint64_t mask : bb_window_masks) {
        if ((mask & opp) != 0) continue;
        int n = std::popcount(mask & me);
        num_windows[n] += 1;
    }
    return num_windows;
}

int get_heuristic_bb(std::uint64_t me, std::uint64_t opp, int parity) {
    ensure_bb_window_masks();
    std::uint64_t occupied = me | opp;
    int ply_count = std::popcount(occupied);
    int my_parity = parity;
    int opp_parity = 1 - parity;

    int score = 0;
    for (std::uint64_t mask : bb_window_masks) {
        int me_count = std::popcount(mask & me);
        int opp_count = std::popcount(mask & opp);

        if (me_count > 0 && opp_count > 0) {
            continue;
        }

        if (me_count == 4) return MATE_SCORE - ply_count;
        if (opp_count == 4) return -(MATE_SCORE - ply_count);
        
        if (me_count > 0) {
            float parity_point = 0.5f;
            std::uint64_t empty_mask = mask & ~me;
            if (empty_mask != 0) {
                int bit_idx = static_cast<int>(std::bit_width(empty_mask) - 1);
                int row = bit_idx % 7;
                bool is_immediate = (row == 0) || ((occupied & (1ULL << (bit_idx - 1))) != 0);
                if (is_immediate && opp_count >= 3) {
                    score += 30;
                }
                parity_point *= (8 - row);
            }
            score += (me_count == 1 ? 1 : (me_count == 2 ? 4 : 30)) * parity_point;
        } else if (opp_count > 0) {
            float parity_point = 0.5f;
            std::uint64_t empty_mask = mask & ~opp;
            if (empty_mask != 0) {
                int bit_idx = static_cast<int>(std::bit_width(empty_mask) - 1);
                int row = bit_idx % 7;
                bool is_immediate = (row == 0) || ((occupied & (1ULL << (bit_idx - 1))) != 0);
                if (is_immediate && opp_count >= 3) {
                    score -= 30;
                }
                parity_point *= (8 - row);
            }
            score -= (opp_count == 1 ? 1 : (opp_count == 2 ? 4 : 30)) * parity_point;
        }
    }

    return score;
}

bool is_win(std::uint64_t b) {
    std::uint64_t m = b & (b << 7);
    if (m & (m << 14)) return true;

    m = b & (b << 1);
    if (m & (m << 2)) return true;

    m = b & (b << 8);
    if (m & (m << 16)) return true;

    m = b & (b << 6);
    if (m & (m << 12)) return true;

    return false;
}

std::pair<std::uint64_t, std::uint64_t> encode_board(const int* board, int board_size, int mark) {
    std::uint64_t me = 0;
    std::uint64_t opp = 0;
    if (board == nullptr || board_size < ROWS * COLUMNS) return {0, 0};

    for (int c = 0; c < COLUMNS; ++c) {
        for (int r = 0; r < ROWS; ++r) {
            int val = board[r * COLUMNS + c];
            if (val == 0) continue;
            std::uint64_t bit = 1ULL << (c * 7 + (ROWS - 1 - r));
            if (val == mark) {
                me |= bit;
            } else {
                opp |= bit;
            }
        }
    }
    return {me, opp};
}

std::vector<int> get_valid_moves(std::uint64_t me, std::uint64_t opp) {
    std::vector<int> moves;
    for (int col : MOVE_ORDER) {
        if (!((me | opp) & (1ULL << (col * 7 + 5)))) {
            moves.push_back(col);
        }
    }
    return moves;
}

std::uint64_t make_move(std::uint64_t me, std::uint64_t opp, int col) {
    std::uint64_t col_mask = (0b111111ULL) << (col * 7);
    std::uint64_t occupied = (me | opp) & col_mask;
    if (occupied & (1ULL << (col * 7 + 5))) return 0;
    return (occupied + (1ULL << (col * 7))) & col_mask;
}

int find_winning_move(std::uint64_t me, std::uint64_t opp) {
    for (int col : MOVE_ORDER) {
        std::uint64_t new_piece = make_move(me, opp, col);
        if (new_piece && is_win(me | new_piece)) return col;
    }
    return -1;
}

std::pair<int, bool> find_forced_block(std::uint64_t me, std::uint64_t opp) {
    std::vector<int> threat_cols;
    for (int col : MOVE_ORDER) {
        std::uint64_t new_piece = make_move(opp, me, col);
        if (new_piece && is_win(opp | new_piece)) threat_cols.push_back(col);
    }

    if (threat_cols.empty()) return {-1, false};
    if (threat_cols.size() == 1) return {threat_cols[0], true};
    return {threat_cols[0], true};
}

} // namespace
