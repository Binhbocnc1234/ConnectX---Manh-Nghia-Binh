#include "OpeningBook.hpp"
#include "Solver.hpp"
#include "Position.hpp"
#include "Position.hpp"
#include <iostream>
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

// Binary record: 8 bytes me + 8 bytes opp + 1 byte move = 17 bytes per entry
// File starts with 4-byte magic "BK01" to detect format
// Python loads using struct.unpack_from('<QQB', buffer, offset)

int main(int argc, char** argv) {
    // --- THIẾT LẬP THAM SỐ HARDCODE ---
    int max_ply = 13;          // Độ sâu tối đa
    int prune_threshold = 4;   // Ngưỡng điểm: Nếu abs(best_score) >= prune_threshold thì không mở rộng nhánh con
    std::string book_in = "..\\7x6.book";         // File đầu vào
    std::string file_out = "opening_book.bin";    // File nhị phân đầu ra (ngay cạnh exe)

    std::cerr << "Exporting book up to ply: " << max_ply
              << ", prune threshold: " << prune_threshold
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

    // Write magic header
    const char magic[4] = {'B', 'K', '0', '1'};
    out.write(magic, 4);

    std::vector<Node> queue;
    std::unordered_set<uint64_t> visited;

    queue.push_back({Position(), 0, 0});

    int count = 0; // Số lượng book hits (best_move != -1)
    int head = 0;
    int misses = 0;
    int max_reached_depth = 0;

    // Ưu tiên cột giữa
    int move_order[7] = {3, 2, 4, 1, 5, 0, 6};

    while (head < (int)queue.size()) {
        Node node = queue[head++];
        
        int current_depth = node.p.nbMoves();
        if (current_depth > max_reached_depth) {
            max_reached_depth = current_depth;
        }

        if (current_depth > max_ply) continue;

        uint64_t key = node.p.key3();
        if (visited.count(key)) continue;
        visited.insert(key);

        int best_move = -1;
        int best_score = -1000;

        // 1. Tìm nước đi tốt nhất từ book
        for (int i = 0; i < 7; i++) {
            int c = move_order[i];
            if (node.p.canPlay(c)) {
                if (node.p.isWinningMove(c)) {
                    best_move = c;
                    best_score = 1000;
                    break;
                }
                Position child = node.p;
                child.playCol(c);
                int val = book.get(child);
                if (val != 0) {
                    int score = -(val + Position::MIN_SCORE - 1);
                    if (score > best_score) {
                        best_score = score;
                        best_move = c;
                    }
                }
                // else if (current_depth >= 13){
                //     int score = -solver.solve(child, false);
                //     if (score > best_score) {
                //         best_score = score;
                //         best_move = c;
                //     }
                // }
            }
        }

        // 2. Ghi nhị phân: uint64 me + uint64 opp + uint8 move (17 bytes)
        if (best_move != -1) {
            out.write(reinterpret_cast<const char*>(&node.me),  8);
            out.write(reinterpret_cast<const char*>(&node.opp), 8);
            uint8_t mv = static_cast<uint8_t>(best_move);
            out.write(reinterpret_cast<const char*>(&mv), 1);
            count++;
        } else {
            misses++;
        }

        // 3. Prune: Nếu thế cờ đã rõ ràng, không mở rộng con
        bool should_expand = true;
        if (best_score == 1000 || (best_score != -1000 && std::abs(best_score) >= prune_threshold)) {
            should_expand = false;
        }

        if (should_expand) {
            for (int i = 0; i < 7; i++) {
                int c = move_order[i];
                if (node.p.canPlay(c) && !node.p.isWinningMove(c)) {
                    int r = 0;
                    for (int bit = 0; bit < 6; bit++) {
                        if ((node.me | node.opp) & (1ULL << (c * 7 + bit))) r++;
                        else break;
                    }
                    Position child = node.p;
                    child.playCol(c);
                    uint64_t child_me  = node.opp;
                    uint64_t child_opp = node.me | (1ULL << (c * 7 + r));
                    queue.push_back({child, child_me, child_opp});
                }
            }
        }

        if (head % 100000 == 0 && head > 0) {
            double hit_rate = (double)count / head * 100.0;
            std::cerr << "Processed " << head << " positions | "
                      << "Hits: " << count << " (" << hit_rate << "%) | "
                      << "Misses: " << misses << " | "
                      << "Max Depth: " << max_reached_depth << " | "
                      << "Queue: " << (queue.size() - head) << std::endl;
            out.flush(); // Cứu dữ liệu nếu bị ngắt ngang
        }
    }

    out.close();
    std::cerr << "Exported " << count << " positions to " << file_out
              << " (" << (count * 17 + 4) / 1024 / 1024 << " MB)" << std::endl;
    return 0;
}