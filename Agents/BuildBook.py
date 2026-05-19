import os
import struct
import time
import json
from collections import deque

from Agents.OpeningBook_optimized import (
    analyze,
    _make_move,
    _canonical_tt_key,
    MOVE_ORDER,
    INVALID_MOVE_SCORE,
)


def nb_moves(me, opp):
    return (me | opp).bit_count()


def export_book(max_ply=12, prune_threshold=120, search_depth=8, timeout_per_node=0.02, file_out=None, format="bin"):
    """
    Export opening book in specified format.
    
    Args:
        max_ply: Maximum ply (half-moves) to search
        prune_threshold: Threshold for pruning positions
        search_depth: Search depth for analyze
        timeout_per_node: Timeout per node analysis
        file_out: Output file path (default: opening_book_score.bin or .json based on format)
        format: "bin" (BK02 binary) or "json" (JSON format)
    """
    if file_out is None:
        ext = ".json" if format == "json" else ".bin"
        file_out = os.path.join(os.path.dirname(__file__), f"opening_book_score{ext}")

    if format not in ("bin", "json"):
        raise ValueError(f"Invalid format: {format}. Must be 'bin' or 'json'")

    print("--- Python Book Builder (BK02) ---")
    print(
        f"max_ply={max_ply}, prune_threshold={prune_threshold}, "
        f"search_depth={search_depth}, timeout_per_node={timeout_per_node}s"
    )
    print(f"format={format}")
    print(f"output={file_out}")

    queue = deque()
    visited = set()
    queue.append((0, 0))

    processed = 0
    pruned_count = 0
    max_reached_depth = 0
    positions = []  # Store all positions for JSON export

    start = time.time()

    if format == "bin":
        out = open(file_out, "wb")
        out.write(b"BK02")
    else:
        out = None

    try:
        while queue:
            me, opp = queue.popleft()
            depth = nb_moves(me, opp)

            if depth > max_reached_depth:
                max_reached_depth = depth

            if depth > max_ply:
                continue

            key64, _ = _canonical_tt_key(me, opp)
            if key64 in visited:
                continue
            visited.add(key64)

            position_score, col_scores = analyze(
                me, opp,
                None,
                timeout=timeout_per_node,
                search_depth=search_depth,
            )
            low_accurate_position_score, low_acc_col_scores = analyze(
                me, opp,
                None,
                timeout=1,
                search_depth=search_depth,
            )
            score_byte = max(-127, min(127, int(position_score/2)))
            
            if format == "bin":
                out.write(struct.pack("<QQb", me, opp, score_byte))
            else:
                positions.append({
                    "me": me,
                    "opp": opp,
                    "value": int(score_byte)
                })
            
            processed += 1

            should_expand = abs(score_byte - max(-127, min(127, int(low_accurate_position_score/2)))) <= prune_threshold
            if not should_expand:
                pruned_count += 1
            else:
                for col in [0,1,2,3,4,5,6]:

                    new_piece = _make_move(me, opp, col)
                    if not new_piece:
                        continue

                    child_me = opp
                    child_opp = me | new_piece
                    queue.append((child_me, child_opp))

            if processed % 100 == 0:
                prune_rate = (pruned_count / processed) * 100.0 if processed else 0.0
                print(
                    f"Processed {processed} | Pruned {pruned_count} ({prune_rate:.1f}%) "
                    f"| MaxDepth {max_reached_depth} | Queue {len(queue)}"
                )
                if format == "bin":
                    out.flush()
    
    finally:
        if format == "bin" and out:
            out.close()
        elif format == "json":
            with open(file_out, "w") as json_out:
                for pos in positions:
                    json_out.write(json.dumps(pos) + "\n")

    size_mb = (processed * 17 + 4) / 1024 / 1024
    print("\n=== Export Complete ===")
    print(f"Total positions processed: {processed}")
    print(f"Positions saved: {processed}")
    print(f"Positions pruned: {pruned_count}")
    print(f"Output file: {file_out}")
    if format == "bin":
        print(f"Size: {size_mb:.2f} MB")
        print("Format: BK02 (me: uint64, opp: uint64, score: int8)")
    else:
        print("Format: JSONL (one {me, opp, value} per line)")
    print(f"Elapsed: {time.time() - start:.2f}s")


def main():
    # Hard-coded configuration (no CLI arguments)
    # Export in BIN format (default, faster and smaller)
    # export_book(
    #     max_ply=12,
    #     prune_threshold=50,
    #     search_depth=16,
    #     timeout_per_node=6,
    #     format="bin",  # Use "bin" or "json"
    #     file_out=os.path.join(os.path.dirname(__file__), "opening_book_score.bin"),
    # )
    
    # Uncomment below to also export in JSON format:
    export_book(
        max_ply=12,
        prune_threshold=50,
        search_depth=16,
        timeout_per_node=6,
        format="json",
        file_out=os.path.join(os.path.dirname(__file__), "opening_book_score.json"),
    )


if __name__ == "__main__":
    main()
