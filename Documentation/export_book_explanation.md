# How `export_book.cpp` Generates Opening Book Entries

## Overview

`export_book.cpp` is a C++ tool that reads Pascal Pons' binary `7x6.book` file (which contains **perfect solutions** for Connect 4 positions) and converts it into a `.jsonl` file our Python agent can read.

The `7x6.book` does NOT store the best move directly. Instead, it stores a **score** for each position (how many moves until the current player wins/loses). Our tool must figure out the best move by trying all 7 columns and picking the one with the highest score.

---

## Step-by-Step Algorithm

### 1. Load the Book
```cpp
OpeningBook book(Position::WIDTH, Position::HEIGHT);
book.load(argv[1]);  // Load 7x6.book (32MB binary file)
```
The book is a hash table where:
- **Key** = `key3()` (a base-3 encoding of the board, symmetric — left-right mirror gives the same key)
- **Value** = 1 byte score (encoded as `score + MIN_SCORE - 1`)

### 2. Initialize BFS from Empty Board
```cpp
queue.push_back({Position(), 0, 0});  // empty board, me=0, opp=0
```
Each node in the queue contains:
- `Position p`: Pascal Pons' internal representation (used to query the book)
- `uint64_t me`: Our Python-compatible bitboard for "current player"
- `uint64_t opp`: Our Python-compatible bitboard for "opponent"

We maintain both representations in parallel because Pascal Pons uses a different internal format (`key3()`) that we can't reconstruct from our bitboard alone.

### 3. For Each Position: Find Best Move
```
For each of 7 columns (in center-first order [3,2,4,1,5,0,6]):
  1. If column is full → skip
  2. If playing here wins immediately → best_move = this column, stop
  3. Otherwise, play the column to create a child Position
  4. Query book.get(child) to get the child's score
  5. The VALUE of this move = -(child's score)
     (because a good score for the opponent is bad for us)
  6. Track the column with the highest value → that's best_move
```

### 4. Output the Entry
```cpp
std::cout << "{\"me\":" << node.me << ",\"opp\":" << node.opp << ",\"move\":" << best_move << "}\n";
```
One JSON line per position, containing:
- `me`: bitboard of the player who is about to move
- `opp`: bitboard of their opponent
- `move`: the perfect column to play (0-6)

### 5. Expand Children (BFS)
```
For each valid, non-winning column c:
  - Compute how many pieces are already in column c (= row r)
  - child_me = node.opp           (opponent becomes "me" in child)
  - child_opp = node.me | (1 << (c*7 + r))  (our piece added to "opp")
  - Push child to queue
```
The `me`/`opp` swap happens because in Connect 4, players alternate turns. After we play, the opponent becomes the active player.

### 6. Deduplication
```cpp
uint64_t key = node.p.key3();  // symmetric base-3 key
if (visited.count(key)) continue;
visited.insert(key);
```
Pascal Pons' `key3()` automatically handles left-right symmetry, so mirror positions are only processed once.

### 7. Depth Limit
```cpp
if (node.p.nbMoves() > MAX_PLY) continue;
```
BFS stops expanding beyond `MAX_PLY` moves. This controls the book size:

| MAX_PLY | Positions | File Size | BFS Queue Peak | Build Time |
|---------|-----------|-----------|----------------|------------|
| 10      | ~1.1M     | ~55MB     | ~5M nodes      | ~1 min     |
| 12      | ~10M+     | ~500MB+   | ~50M+ nodes    | ~10 min    |
| 14      | ~100M+    | >1GB      | OOM risk       | hours+     |

---

## The Exponential Growth Problem

The number of unique Connect 4 positions grows **exponentially** with ply:

```
Ply 0:  1 position
Ply 2:  49 positions (7 × 7)
Ply 4:  ~1,200 positions
Ply 6:  ~20,000 positions
Ply 8:  ~200,000 positions
Ply 10: ~1,100,000 positions
Ply 12: ~10,000,000+ positions
Ply 14: ~100,000,000+ positions  ← OOM crash!
```

Each BFS node in the queue stores a `Position` object (≈40 bytes) plus two `uint64_t` (16 bytes). At ply 14, the queue alone would need **5-10 GB of RAM**.

---

## Why Pruning Would Help

Currently, the BFS visits **every legal position** up to the depth limit. But many of these positions are "easy" — the Python agent's own PVS search can solve them in under 2 seconds anyway. Including them in the book is wasteful during the *build phase* (even if lookups are O(1) at runtime).

### Pruning Strategies:

1. **Score-based pruning**: If the book score for a position indicates one side is winning by a large margin (e.g., |score| > 5), don't expand its children. The Python agent can handle lopsided positions on its own.

2. **Only expand "interesting" branches**: Positions where the score is close to 0 (drawn or slightly favoring one side) are the hardest for the heuristic to evaluate correctly. These are the positions that NEED to be in the book.

3. **DFS instead of BFS**: Use depth-first search with iterative deepening. This uses O(depth) memory instead of O(branching_factor^depth), allowing much deeper exploration.

### Impact:
With score-based pruning (|score| ≤ 10), we could potentially:
- Reach ply 16-20 in the same build time
- Keep the file size under 100MB
- Focus the book on the positions where it matters most
