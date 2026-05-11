#include "core.ipp"

namespace {

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

int pvs(std::uint64_t me, std::uint64_t opp, int depth, int alpha, int beta, double deadline) {
    if (is_win(opp)) {
        int ply_count = std::popcount(me | opp);
        return -(MATE_SCORE - ply_count);
    }
    if (depth == 0 || now_seconds() > deadline) {
        int parity = std::popcount(me | opp) % 2;
        return get_heuristic_bb(me, opp, parity);
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
    std::cout << "[FastAgent] Start turn " << step << std::endl;
    TimePoint start_time = Clock::now();

    double base_timeout = timeout;
    double overage_time = has_overage ? overage : 0.0;
    double think_time_budget = base_timeout * 0.92 + std::min(12.0, overage_time * 3.0 / 5.0);
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
        std::cout << "[FastAgent: Book Hit] Playing precomputed move: " << best_move << std::endl;
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
    int max_search_depth = std::min(28, 42 - std::popcount(me | opp));

    try {
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
    std::cout << "[FastAgent] depth " << reached_depth
              << ", move " << best_move
              << ", time " << std::fixed << std::setprecision(3) << elapsed << "s" << std::endl;
    log_move(best_move, start_time);
    return best_move;
}

} // namespace
