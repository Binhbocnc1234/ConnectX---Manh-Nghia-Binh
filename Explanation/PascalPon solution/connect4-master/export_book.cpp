#include "OpeningBook.hpp"
#include "Position.hpp"
#include <iostream>
#include <vector>
#include <unordered_set>

using namespace GameSolver::Connect4;

struct Node {
    Position p;
    uint64_t me;
    uint64_t opp;
};

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <book_file>" << std::endl;
        return 1;
    }

    OpeningBook book(Position::WIDTH, Position::HEIGHT);
    book.load(argv[1]);

    std::vector<Node> queue;
    std::unordered_set<uint64_t> visited;

    queue.push_back({Position(), 0, 0});
    
    int count = 0;
    int head = 0;
    
    int move_order[7] = {3, 2, 4, 1, 5, 0, 6};

    while (head < queue.size()) {
        Node node = queue[head++];
        
        if (node.p.nbMoves() > 10) continue; // Up to ply 10
        
        uint64_t key = node.p.key3();
        if (visited.count(key)) continue;
        visited.insert(key);

        int best_move = -1;
        int best_score = -1000;

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
            }
        }
        
        if (best_move != -1) {
            std::cout << "{\"me\":" << node.me << ",\"opp\":" << node.opp << ",\"move\":" << best_move << "}\n";
            count++;
        }
        
        // expand children
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
                
                uint64_t child_me = node.opp;
                uint64_t child_opp = node.me | (1ULL << (c * 7 + r));
                
                queue.push_back({child, child_me, child_opp});
            }
        }
        
        if (count % 10000 == 0 && count > 0) {
            std::cerr << "Processed " << count << " positions... Queue size: " << queue.size() - head << std::endl;
        }
    }
    std::cerr << "Exported " << count << " positions." << std::endl;
    return 0;
}
