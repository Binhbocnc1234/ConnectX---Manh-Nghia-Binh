# Opening Book Documentation

The Opening Book is a precomputed database of optimal moves for early-game positions in ConnectX. It allows the agent to play perfect moves instantly during the first several plies, saving valuable thinking time for complex mid-game states.

## Origin

The opening book is generated using a modified version of **PascalPon's Connect4 Solver**. 
- **Source**: Based on the state-of-the-art Alpha-Beta pruning solver implemented in C++.
- **Generation**: We use `export_book_pruned.cpp` to traverse the game tree up to a specific depth (Ply 12) and export the best move for each position.
- **Pruning Strategy**: To keep the book size within Kaggle's 100MB submission limit, we only store positions where the absolute score is high (>= 7), ensuring we prioritize "critical" positions over trivial ones.

## Technical Specifications

### Binary Format (BK01)
Initially, the book was stored in JSONL format, but this proved too slow for the Python environment (taking ~30-60 seconds to load 7M entries). The current system uses a custom binary format (`.bin`):
- **Magic Header**: `BK01` (4 bytes)
- **Record Size**: 17 bytes per entry
- **Data Layout**:
    - `uint64_t me`: Bitboard of the current player's pieces.
    - `uint64_t opp`: Bitboard of the opponent's pieces.
    - `uint8_t move`: The best column index (0-6).

### Symmetry (Mirroring) Optimization
To maximize coverage while minimizing file size, the C++ exporter only saves one "canonical" version of every position (it skips the mirror image if it's identical or already stored).
- **Load-time Mirroring**: When the Python agent loads the book, it automatically calculates the mirrored version of every entry and adds it to the dictionary.
- **Benefit**: This effectively doubles the book's knowledge (handling both left and right-side strategies) with zero lookup overhead during actual gameplay.

## Performance

| Metric | JSONL Format | Binary Format (BK01) |
| :--- | :--- | :--- |
| **Loading Time** | ~45 seconds | **~1.8 seconds** |
| **Memory Usage** | High (String parsing) | Low (Direct `struct` unpacking) |
| **Entries** | ~7.2M raw | ~7.2M raw (**14.4M** with mirrors) |
| **File Size** | ~342 MB | **~122 MB** |

## Usage in Agent

The agent probes the opening book at the start of every turn before starting its own search. If a "Hit" is found, the agent plays the move immediately.
- **Key**: `(me_bitboard, opp_bitboard)` tuple.
- **Complexity**: $O(1)$ average case.
