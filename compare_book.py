import json
import time
import sys

# Import agents
import Agents.ZobristHasingAgent as Zob
from Agents.foundation import encode

# Patch MAX_THINK_TIME to make the test fast
Zob.MAX_THINK_TIME = 0.05

class FakeConfig:
    columns = 7
    rows = 6
    inarow = 4

class FakeObs:
    def __init__(self, board, mark, step):
        self.board = board
        self.mark = mark
        self.step = step
        self.remainingOverageTime = 60

def decode_bitboards(me, opp):
    board = [0] * 42
    for c in range(7):
        for r in range(6):
            bit = 1 << (c * 7 + (5 - r))
            if me & bit:
                board[r * 7 + c] = 1
            elif opp & bit:
                board[r * 7 + c] = 2
    return board

def main():
    book_file = "e:\\small_book.jsonl"
    matches = 0
    total = 0
    
    with open(book_file, "r") as f:
        lines = f.readlines()
        
    print(f"Loaded {len(lines)} positions from small book.")
    
    # Test first 100 positions to save time
    for i, line in enumerate(lines[:100]):
        data = json.loads(line)
        me = data["me"]
        opp = data["opp"]
        book_move = data["move"]
        
        # Determine step by counting pieces
        ply = me.bit_count() + opp.bit_count()
        
        board = decode_bitboards(me, opp)
        obs = FakeObs(board, 1, ply)
        config = FakeConfig()
        
        agent_move = Zob.agent(obs, config)
        
        if agent_move == book_move:
            matches += 1
            match_str = "MATCH"
        else:
            match_str = "DIFF "
            
        print(f"Pos {i+1:3d} (Ply {ply:2d}): Book={book_move}, Agent={agent_move} [{match_str}]")
        total += 1
        
    print(f"\\nMatch rate: {matches}/{total} ({matches/total*100:.1f}%)")
    print("If the match rate is reasonable (>30%), it means the conversion logic is correct,")
    print("but the heuristic isn't perfect (which is why we need the book!).")

if __name__ == "__main__":
    main()
