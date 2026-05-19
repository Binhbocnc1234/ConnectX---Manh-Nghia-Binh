#include "OpeningBook.hpp"
#include "Solver.hpp"
#include "Position.hpp"
#include <iostream>
#include <deque>
#include <vector>
#include <unordered_set>
#include <fstream>
#include <cmath>
#include <cstdint>

using namespace GameSolver::Connect4;

struct Node {
    Position p;
    uint64_t me;
    uint64_t opp;
};

// Binary record: 8 bytes me + 8 bytes opp + 1 byte score = 17 bytes per entry
// File starts with 4-byte magic "BK02" to detect new format
// Python loads using struct.unpack_from('<QQb', buffer, offset)

int main(int argc, char** argv) {
    // --- SETUP PARAMETERS ---
    int max_ply = 12;              // Maximum depth to explore
    int prune_threshold = 4;      // Score threshold: if abs(score) >= threshold, don't expand children
    std::string book_in = "..\\7x6.book";
    std::string file_out = "opening_book_score.bin";
    std::cerr << "Exporting book up to ply: " << max_ply
              << ", prune_threshold: " << prune_threshold
              << ", output: " << file_out << std::endl;

    OpeningBook book(Position::WIDTH, Position::HEIGHT);
    book.load(book_in);
    Solver solver;
    solver.loadBook(book_in);

    std::ofstream out(file_out, std::ios::binary);
    if (!out.is_open()) {
        std::cerr << "Cannot open output file: " << file_out << std::endl;
        return 1;
    }

    // Write magic header for new format
    const char magic[4] = {'B', 'K', '0', '2'};
    out.write(magic, 4);

    std::deque<Node> queue;
    std::unordered_set<uint64_t> visited;

    queue.push_back({Position(), 0, 0});

    int processed = 0;       // Number of positions processed and saved
    int pruned_count = 0;    // Number of positions pruned
    int max_reached_depth = 0;

    // Priority: center columns first
    int move_order[7] = {3, 2, 4, 1, 5, 0, 6};

    while (!queue.empty()) {
        Node node = queue.front();
        queue.pop_front();
        
        int current_depth = node.p.nbMoves();
        if (current_depth > max_reached_depth) {
            max_reached_depth = current_depth;
        }

        if (current_depth > max_ply) {
            continue;
        }

        uint64_t key = node.p.key3();
        if (visited.count(key)) {
            continue;
        }
        visited.insert(key);

        // --- STEP 1: Get score for current position from book ---
        int position_score = 0;
        int val = book.get(node.p);  // 1-byte encoded score from book
        if (val != 0) {
            position_score = val + Position::MIN_SCORE - 1;  // Decode to solver range
        } else {
            position_score = solver.solve(node.p, false);    // Compute if not in book
        }

        // --- STEP 2: Save this position with its score ---
        out.write(reinterpret_cast<const char*>(&node.me), 8);
        out.write(reinterpret_cast<const char*>(&node.opp), 8);
        int8_t score_byte = static_cast<int8_t>(position_score);
        out.write(reinterpret_cast<const char*>(&score_byte), 1);
        processed++;

        // --- STEP 3: Decide whether to expand children ---
        bool should_expand = true;
        if (std::abs(position_score) >= prune_threshold - current_depth/5) {
            // Position is decided (win/loss within <= ply)
            // Python agent can handle these, so PRUNE
            should_expand = false;
            pruned_count++;
        }

        // --- STEP 4: Expand children if not pruned ---
        if (should_expand) {
            // Use analyze() to get scores for all columns
            std::vector<int> col_scores = solver.analyze(node.p, false);

            for (int i = 0; i < 7; i++) {
                int c = move_order[i];
                if (col_scores[c] == Solver::INVALID_MOVE) {
                    continue;  // Column full or invalid
                }

                // Calculate row where piece lands
                int r = 0;
                for (int bit = 0; bit < 6; bit++) {
                    if ((node.me | node.opp) & (1ULL << (c * 7 + bit))) {
                        r++;
                    } else {
                        break;
                    }
                }

                if (r >= 6) {
                    continue;  // Column is full
                }

                Position child = node.p;
                child.playCol(c);

                // Create child node with flipped me/opp (since turn changes)
                uint64_t child_me = node.opp;
                uint64_t child_opp = node.me | (1ULL << (c * 7 + r));

                queue.push_back({child, child_me, child_opp});
            }
        }

        // Progress reporting
        if (processed % 10000 == 0 && processed > 0) {
            double prune_rate = processed > 0 ? (double)pruned_count / processed * 100.0 : 0.0;
            std::cerr << "Processed " << processed << " positions | "
                      << "Pruned: " << pruned_count << " (" << prune_rate << "%) | "
                      << "Max Depth: " << max_reached_depth << " | "
                      << "Queue: " << queue.size() << std::endl;
            out.flush();
        }
    }

    out.close();
    
    int file_size_mb = (processed * 17 + 4) / 1024 / 1024;
    std::cerr << "\n=== Export Complete ===" << std::endl;
    std::cerr << "Total positions processed: " << processed << std::endl;
    std::cerr << "Positions saved: " << processed << std::endl;
    std::cerr << "Positions pruned: " << pruned_count << std::endl;
    std::cerr << "Output file: " << file_out << " (" << file_size_mb << " MB)" << std::endl;
    std::cerr << "Format: BK02 (me: uint64, opp: uint64, score: int8)" << std::endl;

    return 0;
}
