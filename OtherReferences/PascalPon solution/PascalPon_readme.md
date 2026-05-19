# Connect 4 Game Solver

This C++ source code is published under AGPL v3 license.

Read the associated [step by step tutorial to build a perfect Connect 4 AI](http://blog.gamesolver.org) for explanations.

## Notes about Pascal Pon's book and the exporters

Pascal Pon's original `7x6.book` is not a move list. It is a position database built on top of a transposition-table-style structure:

- each entry is keyed by a position key
- each stored value is 1 byte
- the value encodes the score of that position, not the best move
- `0` means the entry is empty or missing

Because of that, `best_move` must be reconstructed by the exporter:

1. Try every legal column in a fixed move order.
2. If a move is an immediate win, keep it.
3. Otherwise play the move, query `book.get(child)`, decode the child's score, then negate it to evaluate the move from the current player's point of view.
4. Keep the column with the highest derived score.

The current formula used in both `export_book.cpp` and `export_book_pruned.cpp` is therefore correct:

```cpp
int score = -(val + Position::MIN_SCORE - 1);
```

Here `val` is the encoded score returned by `book.get(child)`, `Position::MIN_SCORE - 1` decodes the stored byte back into the solver score range, and the outer minus sign converts the child's score into the current player's perspective.

Exporter summary:

- `export_book.cpp` writes JSONL records with `me`, `opp`, and `move`.
- `export_book_pruned.cpp` writes a compact binary format with the `BK02` magic header and 17-byte records: `uint64 me`, `uint64 opp`, `int8 position_score`.
- `export_book_pruned.cpp` also stops expanding branches when a position is already clearly decided (based on `position_score`), so the output stays smaller.
- Compile command : g++ -O3 export_book_pruned.cpp Solver.cpp -o export_book_pruned.exe
- Run command : ./export_book_pruned
In short: Pascal Pon's book stores position scores, while these exporters make that information available to the Python agent.

### Understanding `position_score` in export_book_pruned.cpp

`position_score` is the **minimax evaluation score** of a position from Pascal Pon's solver:

```cpp
int val = book.get(node.p);  // 1-byte encoded score from book
if (val != 0) {
    position_score = val + Position::MIN_SCORE - 1;  // Decode to solver range
} else {
    position_score = solver.solve(node.p, false);    // Compute if not in book
}
```

**Meaning and semantics:**
- **Score Range**: approximately **-22 to +22** (can win/lose within 21 plies)
  - `Position::MIN_SCORE = -(7×6)/2 + 3 = -18`
  - `Position::MAX_SCORE = (7×6+1)/2 - 3 = 20`
- **Score Semantics**:
  - **Negative score** (e.g., -5): Current player will lose with optimal play from opponent
  - **Zero** (0): Draw with optimal play from both sides
  - **Positive score** (e.g., +8): Current player will win with optimal play
- **Score Magnitude**: Represents how many plies (half-moves) into the future the game is decided
  - Example: `|score| = 12` means the outcome is decided within ≈6 full moves

**Role in pruning:**
- If `abs(position_score) >= prune_threshold` (e.g., 12), the position is considered "decided"
- Decided positions are **not expanded** (no children added to export)
- Rationale: Python agent's search can independently verify these outcomes, so they don't need to be in the book
- Result: Only "uncertain" positions (where `|score| < threshold`) are exported, making the book file smaller while keeping strategic guidance

**Example:**
- Position with `position_score = 18` and `prune_threshold = 12`: **PRUNED** (current player wins decisively, Python can find it)
- Position with `position_score = 5` and `prune_threshold = 12`: **EXPORTED** (uncertain outcome, needs Pascal Pon's guidance)

## Workflow: From Agent Call to Move Output

When a Connect 4 agent using Pascal Pon's solver is asked to move, the execution flow is as follows:

```
Agent.solve(position) [Entry point]
    ↓
    ├─→ Solver::solve(Position P, weak=false)
    │       ├─→ Check if P.canWinNext() [immediate win?]
    │       │   └─→ If yes, return (WIDTH × HEIGHT + 1 - nbMoves) / 2
    │       │
    │       └─→ Iteratively narrow search window using binary search on scores
    │           └─→ Call Solver::negamax(P, alpha, beta) repeatedly
    │
    └─→ Solver::negamax(Position P, int alpha, int beta)
            ├─→ Check transposition table (cache of previously solved positions)
            │
            ├─→ Check OpeningBook::get(P)
            │   ├─→ Load from 7x6.book (or exported variant)
            │   ├─→ Hash key = Position::key3() [symmetric position encoding]
            │   └─→ Lookup value in TranspositionTable (position → 1-byte score)
            │
            ├─→ Generate legal moves using MoveSorter (center-first ordering)
            │
            ├─→ For each move:
            │   ├─→ Play move on a child Position
            │   ├─→ Recursively call negamax(child, -beta, -alpha)
            │   ├─→ Apply alpha-beta pruning
            │   └─→ Store result in transposition table if better bound found
            │
            └─→ Return best score found
```

### Key Files Involved

| File | Role |
|------|------|
| `main.cpp` | Entry point; reads position sequences and calls solver |
| `Solver.hpp/cpp` | Core solver logic: `solve()` and `negamax()` algorithms |
| `OpeningBook.hpp` | Book loading and lookup interface |
| `TranspositionTable.hpp` | Hash table for storing position → score mappings |
| `Position.hpp` | Board representation; bitboard operations; move generation |
| `MoveSorter.hpp` | Move ordering heuristic (center columns first) |
| `7x6.book` | Pre-computed binary database of position scores |

### Data Flow

1. **Position Creation**: A `Position` object encodes the board state as two bitboards (`current_player`, `mask`) and uses `key3()` for symmetric hashing.
2. **Book Lookup**: If a position is in the opening book (via transposition table lookup), the encoded score is returned immediately.
3. **Search**: If not in the book, `negamax()` recursively explores the game tree with alpha-beta pruning.
4. **Caching**: All searched positions are stored in the transposition table to avoid re-computing.
5. **Move Selection**: The best move is the one that led to the best score in the search tree.

### Example Sequence

```
Solver::solve(empty board)
  → negamax(empty board, -22, 22)
    → Lookup book: Position "no moves yet" → found, return encoded score
    → If not in book:
        → Generate 7 possible first moves
        → For each move: play it, negate its minimax value, track best
        → Store result: (empty board key → best score) in transposition table
  → Return the move that gave the best score
```

### Meaning of `Solver::solve()`

`Solver::solve(const Position& P, bool weak=false)` is the solver entry point that returns a minimax score for position `P` expressed in plies (half-moves). Its behavior in brief:

- Quick checks: it first tests for immediate wins/losses such as `P.canWinNext()` and returns a direct score when the position is decided by a single move. The code often uses the helper expression `(WIDTH * HEIGHT + 1 - nbMoves) / 2` to compute the remaining "moves by side" for these terminal cases.
- Opening book: `negamax()` consulted by `solve()` checks the opening book / transposition table and will return the stored 1-byte encoded score when available.
- Search loop: when the book does not contain an exact value, `solve()` performs an iterative narrowing of the score window (a binary search over possible scores) and repeatedly calls `negamax(P, alpha, beta)` until the exact minimax value is found.
- Return value semantics: the returned integer is in "plies" (half-moves):
  - Positive `+N`: the side to move wins with optimal play in `N` plies.
  - Negative `-N`: the side to move will lose (the opponent wins) in `N` plies.
  - `0`: theoretically a draw (or no forced win/loss within solver bounds).

Examples:
- `solve(P) == +8` → side to move wins in 8 plies (i.e., 4 full moves).
- `solve(P) == -7` → opponent wins in 7 plies; the opponent completes the win on their 4th move (ceil(7/2) = 4).

This is the exact same score representation stored inside `7x6.book` (after decoding the stored byte using `Position::MIN_SCORE - 1`), which is why exporters decode the 1-byte value into this score range before writing it out.
