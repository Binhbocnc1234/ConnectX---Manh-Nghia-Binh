#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

// Game constants and search/scoring constants are kept identical to Python logic.
constexpr int ROWS = 6;
constexpr int COLUMNS = 7;
constexpr int INAROW = 4;

constexpr int INF = 1000000;
constexpr int NNF = -1000000;
constexpr int MATE_SCORE = 100000;

constexpr int TT_BUCKETS = 1 << 23;
constexpr int TT_BUCKET_MASK = TT_BUCKETS - 1;
constexpr int TT_BUCKET_SIZE = 4;

constexpr int TT_EXACT = 0;
constexpr int TT_LOWER = 1;
constexpr int TT_UPPER = 2;

const std::array<int, 7> MOVE_ORDER = {3, 2, 4, 1, 5, 0, 6};

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

struct TimeoutError : public std::exception {
    const char* what() const noexcept override { return "timeout"; }
};

struct TTEntry {
    std::uint64_t key;
    int depth;
    int value;
    int flag;
    int best_move;
};

struct PairHash {
    std::size_t operator()(const std::pair<std::uint64_t, std::uint64_t>& p) const noexcept {
        std::uint64_t x = p.first;
        std::uint64_t y = p.second;
        std::uint64_t h = x ^ (y + 0x9e3779b97f4a7c15ULL + (x << 6) + (x >> 2));
        return static_cast<std::size_t>(h);
    }
};

std::unordered_map<int, std::vector<TTEntry>> tt;
std::unordered_map<int, std::array<int, 2>> killer_moves;
std::unordered_map<std::pair<std::uint64_t, std::uint64_t>, int, PairHash> opening_book;
bool opening_book_loaded = false;
std::string engine_base_dir;

std::array<std::uint64_t, 49> Z_ME{};
std::array<std::uint64_t, 49> Z_OPP{};
bool zobrist_ready = false;

std::vector<std::uint64_t> bb_window_masks;
bool bb_window_masks_ready = false;

// Shared monotonic clock helper used for timeout checks and runtime logging.
inline double now_seconds() {
    auto now = Clock::now().time_since_epoch();
    return std::chrono::duration<double>(now).count();
}

int ipow(int base, int exp) {
    int result = 1;
    for (int i = 0; i < exp; ++i) result *= base;
    return result;
}

std::string format_int_list(const std::vector<int>& values) {
    std::ostringstream oss;
    oss << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << values[i];
    }
    oss << "]";
    return oss.str();
}

std::uint64_t mirror_board(std::uint64_t bb) {
    std::uint64_t m = 0;
    m |= (bb & 0x7FULL) << 42;
    m |= (bb & (0x7FULL << 7)) << 28;
    m |= (bb & (0x7FULL << 14)) << 14;
    m |= (bb & (0x7FULL << 21));
    m |= (bb & (0x7FULL << 28)) >> 14;
    m |= (bb & (0x7FULL << 35)) >> 28;
    m |= (bb & (0x7FULL << 42)) >> 42;
    return m;
}

std::uint64_t splitmix64(std::uint64_t x) {
    x = (x + 0x9E3779B97F4A7C15ULL) & 0xFFFFFFFFFFFFFFFFULL;
    std::uint64_t z = x;
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL) & 0xFFFFFFFFFFFFFFFFULL;
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EBULL) & 0xFFFFFFFFFFFFFFFFULL;
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFFULL;
}

void ensure_zobrist() {
    if (zobrist_ready) return;
    std::uint64_t x = 0xC0FFEEULL & 0xFFFFFFFFFFFFFFFFULL;
    for (int i = 0; i < 49; ++i) {
        x = splitmix64(x);
        Z_ME[i] = x;
        x = splitmix64(x);
        Z_OPP[i] = x;
    }
    zobrist_ready = true;
}

std::uint64_t zobrist_hash(std::uint64_t me, std::uint64_t opp) {
    ensure_zobrist();
    std::uint64_t h = 0;
    std::uint64_t bb = me;
    while (bb) {
        std::uint64_t lsb = bb & (~bb + 1ULL);
        int idx = static_cast<int>(std::countr_zero(lsb));
        h ^= Z_ME[idx];
        bb ^= lsb;
    }
    bb = opp;
    while (bb) {
        std::uint64_t lsb = bb & (~bb + 1ULL);
        int idx = static_cast<int>(std::countr_zero(lsb));
        h ^= Z_OPP[idx];
        bb ^= lsb;
    }
    return h & 0xFFFFFFFFFFFFFFFFULL;
}

// Canonical key picks original/mirrored orientation with deterministic tie-breaking.
std::pair<std::uint64_t, bool> canonical_tt_key(std::uint64_t me, std::uint64_t opp) {
    std::uint64_t key = zobrist_hash(me, opp);
    std::uint64_t m_me = mirror_board(me);
    std::uint64_t m_opp = mirror_board(opp);
    std::uint64_t m_key = zobrist_hash(m_me, m_opp);
    if ((m_key < key) || (m_key == key && std::make_pair(m_me, m_opp) < std::make_pair(me, opp))) {
        return {m_key, true};
    }
    return {key, false};
}

struct TTProbeResult {
    bool has_value;
    int value;
    int alpha;
    int beta;
    int best_hint;
};

TTProbeResult tt_probe(std::uint64_t key64, int depth, int alpha, int beta) {
    int idx = static_cast<int>(key64 & TT_BUCKET_MASK);
    auto it = tt.find(idx);
    if (it == tt.end()) return {false, 0, alpha, beta, -1};

    int best_hint = -1;
    int best_hint_depth = -1;

    for (const auto& e : it->second) {
        if (e.key != key64) continue;
        if (e.best_move != -1 && e.depth > best_hint_depth) {
            best_hint = e.best_move;
            best_hint_depth = e.depth;
        }
        if (e.depth < depth) continue;

        if (e.flag == TT_EXACT) return {true, e.value, alpha, beta, e.best_move};
        if (e.flag == TT_LOWER) {
            if (e.value > alpha) alpha = e.value;
        } else if (e.flag == TT_UPPER) {
            if (e.value < beta) beta = e.value;
        }
        if (alpha >= beta) return {true, e.value, alpha, beta, e.best_move};
    }

    return {false, 0, alpha, beta, best_hint};
}

// Bucketed transposition-table replacement policy matches Python behavior.
void tt_store(std::uint64_t key64, int depth, int value, int flag, int best_move) {
    int idx = static_cast<int>(key64 & TT_BUCKET_MASK);
    TTEntry entry{key64, depth, value, flag, best_move};
    auto& bucket = tt[idx];

    for (auto& e : bucket) {
        if (e.key == key64) {
            if (depth >= e.depth) e = entry;
            return;
        }
    }

    if (static_cast<int>(bucket.size()) < TT_BUCKET_SIZE) {
        bucket.push_back(entry);
        return;
    }

    int victim_i = 0;
    int victim_depth = bucket[0].depth;
    for (int i = 1; i < static_cast<int>(bucket.size()); ++i) {
        if (bucket[i].depth < victim_depth) {
            victim_depth = bucket[i].depth;
            victim_i = i;
        }
    }
    bucket[victim_i] = entry;
}

// Precompute all 4-cell line masks once for fast bitboard heuristic evaluation.
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

int get_heuristic_bb(std::uint64_t me, std::uint64_t opp) {
    auto num_opp = count_windows_bb(opp, me);
    for (int i = 0; i < INAROW; ++i) {
        if (i == (INAROW - 1) && num_opp[i + 1] >= 1) {
            int ply_count = std::popcount(me | opp);
            return -(MATE_SCORE - ply_count);
        }
    }

    auto num = count_windows_bb(me, opp);
    for (int i = 0; i < INAROW; ++i) {
        if (i == (INAROW - 1) && num[i + 1] >= 1) {
            int ply_count = std::popcount(me | opp) + 1;
            return (MATE_SCORE - ply_count);
        }
    }

    int score = 0;
    for (int i = 0; i < INAROW; ++i) score += ipow(4, i) * num[i + 1];
    for (int i = 0; i < INAROW; ++i) score -= ipow(4, i) * num_opp[i + 1];
    return score;
}

// Bitboard win detection by directional shift-and-match checks.
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

// Threat pre-check helpers to detect immediate wins / forced blocks before deep search.
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

// Killer-move tracking keeps strong cutoff candidates by depth.
void record_killer(int depth, int col) {
    auto it = killer_moves.find(depth);
    if (it == killer_moves.end()) {
        killer_moves[depth] = {col, -1};
    } else if (it->second[0] != col) {
        it->second[1] = it->second[0];
        it->second[0] = col;
    }
}

std::array<int, 2> get_killer(int depth) {
    auto it = killer_moves.find(depth);
    if (it == killer_moves.end()) return {-1, -1};
    return it->second;
}

// Principal Variation Search with TT bounds, killer ordering and null-window re-search.
int pvs(std::uint64_t me, std::uint64_t opp, int depth, int alpha, int beta, double deadline) {
    if (is_win(opp)) {
        int ply_count = std::popcount(me | opp);
        return -(MATE_SCORE - ply_count);
    }
    if (depth == 0 || now_seconds() > deadline) {
        return get_heuristic_bb(me, opp);
    }

    int alpha0 = alpha;
    int beta0 = beta;

    auto [key64, flip] = canonical_tt_key(me, opp);
    auto probe = tt_probe(key64, depth, alpha, beta);
    alpha = probe.alpha;
    beta = probe.beta;
    int tt_best = probe.best_hint;
    if (probe.has_value) return probe.value;

    if (tt_best != -1 && flip) tt_best = 6 - tt_best;

    int value = NNF;
    int best_move = -1;
    bool first_child = true;

    std::vector<int> ordered;
    ordered.reserve(7);
    if (tt_best != -1) ordered.push_back(tt_best);

    auto killers = get_killer(depth);
    for (int k : killers) {
        if (k != -1 && std::find(ordered.begin(), ordered.end(), k) == ordered.end()) {
            ordered.push_back(k);
        }
    }

    for (int c : MOVE_ORDER) {
        if (std::find(ordered.begin(), ordered.end(), c) == ordered.end()) {
            ordered.push_back(c);
        }
    }

    for (int col : ordered) {
        std::uint64_t col_mask = (0b111111ULL) << (col * 7);
        std::uint64_t occupied = (me | opp) & col_mask;
        if (occupied & (1ULL << (col * 7 + 5))) continue;

        std::uint64_t new_piece = (occupied + (1ULL << (col * 7))) & col_mask;
        int res;

        if (first_child) {
            res = -pvs(opp, me | new_piece, depth - 1, -beta, -alpha, deadline);
            first_child = false;
        } else {
            res = -pvs(opp, me | new_piece, depth - 1, -alpha - 1, -alpha, deadline);
            if (alpha < res && res < beta) {
                res = -pvs(opp, me | new_piece, depth - 1, -beta, -res, deadline);
            }
        }

        if (res > value) {
            value = res;
            best_move = col;
        }
        alpha = std::max(alpha, value);
        if (alpha >= beta) {
            record_killer(depth, col);
            break;
        }
    }

    int store_move = (best_move != -1) ? (flip ? 6 - best_move : best_move) : -1;
    int flag;
    if (value <= alpha0) {
        flag = TT_UPPER;
    } else if (value >= beta0) {
        flag = TT_LOWER;
    } else {
        flag = TT_EXACT;
    }

    tt_store(key64, depth, value, flag, store_move);
    return value;
}

std::uint64_t read_u64_le(const char* ptr) {
    std::uint64_t v = 0;
    for (int i = 0; i < 8; ++i) {
        v |= (static_cast<std::uint64_t>(static_cast<unsigned char>(ptr[i])) << (8 * i));
    }
    return v;
}

void load_opening_book() {
    if (opening_book_loaded) return;
    opening_book_loaded = true;
    opening_book.clear();

    std::filesystem::path current_dir = engine_base_dir.empty()
        ? std::filesystem::current_path()
        : std::filesystem::path(engine_base_dir);

    std::filesystem::path book_path = current_dir / "opening_book.bin";

    if (std::filesystem::exists(book_path)) {
        int count = 0;
        try {
            std::ifstream in(book_path, std::ios::binary);
            if (!in) {
                throw std::runtime_error("cannot open file");
            }

            char magic[4] = {0, 0, 0, 0};
            in.read(magic, 4);
            if (in.gcount() != 4 || std::string(magic, 4) != "BK01") {
                std::cout << "[Opening Book] Warning: " << book_path.string()
                          << " is not in expected BK01 binary format." << std::endl;
                return;
            }

            std::vector<char> raw_data((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
            constexpr int entry_size = 17;
            int num_entries = static_cast<int>(raw_data.size() / entry_size);

            for (int i = 0; i < num_entries; ++i) {
                if (i == num_entries / 4) {
                    std::cout << "[Opening Book] Loading... 25%" << std::endl;
                } else if (i == num_entries / 2) {
                    std::cout << "[Opening Book] Loading... 50%" << std::endl;
                } else if (i == (num_entries * 3) / 4) {
                    std::cout << "[Opening Book] Loading... 75%" << std::endl;
                }

                const char* p = raw_data.data() + i * entry_size;
                std::uint64_t me = read_u64_le(p);
                std::uint64_t opp = read_u64_le(p + 8);
                int move = static_cast<unsigned char>(p[16]);

                opening_book[{me, opp}] = move;

                std::uint64_t m_me = mirror_board(me);
                std::uint64_t m_opp = mirror_board(opp);
                if (std::make_pair(m_me, m_opp) != std::make_pair(me, opp)) {
                    opening_book[{m_me, m_opp}] = 6 - move;
                }

                count += 1;
            }

            std::cout << "[Opening Book] Loading... 100%" << std::endl;
            std::cout << "[Opening Book] Loaded " << count << " positions (" << opening_book.size()
                      << " entries with mirror) from " << book_path.string() << " (Binary)." << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[Opening Book] Error loading binary book: " << e.what() << std::endl;
        }
    } else {
        std::filesystem::path old_path = current_dir / "small_book_pruned.jsonl";
        if (std::filesystem::exists(old_path)) {
            std::cout << "[Opening Book] Warning: binary book not found, please re-export using export_book_pruned.cpp for faster loading." << std::endl;
        } else {
            std::cout << "[Opening Book] Warning: No opening book found at " << book_path.string() << std::endl;
        }
    }
}

void log_move(int /*move*/, const TimePoint& /*start_time*/) {
    // Intentionally no-op to preserve current Python behavior.
}

int choose_center_closest(const std::vector<int>& valid_moves, int center_col) {
    int best = valid_moves[0];
    int best_dist = std::abs(best - center_col);
    for (int m : valid_moves) {
        int d = std::abs(m - center_col);
        if (d < best_dist) {
            best = m;
            best_dist = d;
        }
    }
    return best;
}

int opening_book_opt_agent_impl(
    const int* board,
    int board_size,
    int mark,
    int step,
    int columns,
    double timeout,
    bool has_overage,
    double overage
) {
    // Keep user-visible stdout flow compatible with the Python implementation.
    std::cout << "[OpeningBookOpt] Start turn " << step << std::endl;
    TimePoint start_time = Clock::now();

    double base_timeout = timeout;
    double overage_time = has_overage ? overage : 0.0;
    bool is_first_turn = (step == 0 || step == 1);

    double think_time_budget;
    if (is_first_turn) {
        think_time_budget = base_timeout + std::min(overage_time, 55.0);
        std::cout << "[OpeningBookOpt] First turn. Budget: "
                  << std::fixed << std::setprecision(1) << think_time_budget
                  << "s (incl. overage)" << std::endl;
    } else {
        think_time_budget = base_timeout * 0.92;
    }

    double deadline = now_seconds() + think_time_budget;

    auto [me, opp] = encode_board(board, board_size, mark);

    load_opening_book();

    int win_col = find_winning_move(me, opp);
    if (win_col != -1) {
        std::cout << "[Instant Win] Playing column " << win_col << std::endl;
        log_move(win_col, start_time);
        return win_col;
    }

    auto [block_col, must_block] = find_forced_block(me, opp);
    if (must_block) {
        auto valid = get_valid_moves(me, opp);
        if (std::find(valid.begin(), valid.end(), block_col) != valid.end()) {
            std::cout << "[Forced Block] Must block opponent at column " << block_col << std::endl;
            log_move(block_col, start_time);
            return block_col;
        }
    }

    auto it_book = opening_book.find({me, opp});
    if (it_book != opening_book.end()) {
        int best_move = it_book->second;
        std::cout << "[Opening Book Hit] Playing precomputed move: " << best_move << std::endl;
        log_move(best_move, start_time);
        return best_move;
    }

    auto [key64, flip] = canonical_tt_key(me, opp);
    int tt_hint_move = -1;
    int idx = static_cast<int>(key64 & TT_BUCKET_MASK);
    auto it_bucket = tt.find(idx);
    if (it_bucket != tt.end()) {
        int best_d = -1;
        for (const auto& e : it_bucket->second) {
            if (e.key == key64 && e.best_move != -1 && e.depth > best_d) {
                tt_hint_move = e.best_move;
                best_d = e.depth;
            }
        }
        if (tt_hint_move != -1 && flip) tt_hint_move = 6 - tt_hint_move;
    }

    auto valid_moves = get_valid_moves(me, opp);
    if (valid_moves.empty()) return 0;

    int center_col = columns / 2;
    int best_move = (tt_hint_move != -1 && std::find(valid_moves.begin(), valid_moves.end(), tt_hint_move) != valid_moves.end())
        ? tt_hint_move
        : choose_center_closest(valid_moves, center_col);

    int reached_depth = 0;
    int max_search_depth = is_first_turn ? 30 : 24;

    try {
        // Iterative deepening loop (depth 0,2,4,...) with per-depth score reporting.
        for (int depth = 0; depth < max_search_depth; depth += 2) {
            int best_score = NNF;
            int move_at_this_depth = best_move;
            std::vector<int> scores(columns, NNF);

            std::vector<int> moves;
            moves.reserve(valid_moves.size());
            moves.push_back(best_move);
            for (int m : valid_moves) {
                if (m != best_move) moves.push_back(m);
            }

            for (std::size_t i = 0; i < moves.size(); ++i) {
                int col = moves[i];
                if (now_seconds() > deadline) throw TimeoutError();

                std::uint64_t new_piece = make_move(me, opp, col);
                if (!new_piece) continue;

                if (is_win(me | new_piece)) {
                    log_move(col, start_time);
                    return col;
                }

                int score;
                if (i == 0) {
                    score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline);
                } else {
                    if (best_score == NNF) {
                        score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline);
                    } else {
                        score = -pvs(opp, me | new_piece, depth, -best_score - 1, -best_score, deadline);
                        if (best_score < score && score < INF) {
                            score = -pvs(opp, me | new_piece, depth, NNF, INF, deadline);
                        }
                    }
                }

                scores[col] = score;
                if (score > best_score) {
                    best_score = score;
                    move_at_this_depth = col;
                }
            }

            best_move = move_at_this_depth;
            std::cout << "At depth: " << depth << " Best move: " << best_move << " " << format_int_list(scores) << std::endl;
            reached_depth = depth;
            if (best_score >= MATE_SCORE - 42) break;
        }
    } catch (const TimeoutError&) {
    }

    auto elapsed = std::chrono::duration<double>(Clock::now() - start_time).count();
    std::cout << "[OpeningBook_opt] depth " << reached_depth
              << ", move " << best_move
              << ", time " << std::fixed << std::setprecision(3) << elapsed << "s" << std::endl;
    log_move(best_move, start_time);
    return best_move;
}

}  // namespace
