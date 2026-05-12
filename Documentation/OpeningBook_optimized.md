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



## 5. Luồng thực thi của Agent tối ưu nhất (`OpeningBook_optimized.py`)
Luồng thực thi của phiên bản tối ưu nhất được thiết kế để kết hợp sức mạnh tra cứu ngay lập tức (O(1)) của Opening Book và khả năng tìm kiếm sâu sắc của PVS.

Khi môi trường truyền trạng thái bàn cờ (`obs`) vào hàm `agent(obs, config)`, quy trình diễn ra như sau:

**Bước 1: Tính toán thời gian & Nạp Dữ liệu**
*   Xác định **Thinking Time Budget**: Theo luật chơi
*   Kiểm tra và tự động nạp `opening_book.jsonl` vào RAM nếu chưa nạp. Hàm `encode` sẽ phân tích ma trận bàn cờ thành 2 số nguyên 64-bit (`me` và `opp`).

**Bước 2: Kiểm tra thắng nhanh & Chặn đe dọa (Forced-move Block)**
*   **Kiểm tra Thắng ngay**: Nếu có bất kỳ cột nào giúp Agent tạo thành 4 quân liên tiếp ngay lập tức, đi ngay vào cột đó để thắng ván.
*   **Chặn đe dọa**: Nếu đối phương chuẩn bị thắng ở nước kế tiếp, lập tức đi vào cột chặn đe dọa đó (Forced block) mà không cần search sâu.

**Bước 3: Tìm kiếm Siêu tốc (Fast Path) qua Sách Khai Cuộc**
*   Agent tính mã băm chuẩn (Canonical Zobrist Hash) của thế cờ hiện tại. Nó sẽ lật ngược bàn cờ (Symmetry) để tính mã băm đối xứng, sau đó chọn mã nhỏ nhất làm `key64`.
*   Truy vấn trực tiếp `key64` vào từ điển `OPENING_BOOK`.
*   **Nếu có (Hit):** Agent lập tức trả về nước đi `best_move` (điều chỉnh lại lật phải/trái nếu cần). Bỏ qua toàn bộ bước thuật toán phức tạp phía dưới. Thời gian suy nghĩ gần như bằng 0s.

**Bước 4: Tham vấn Bảng băm (Transposition Table Hint)**
*   Nếu thế cờ không nằm trong Book (tức là đã bước vào giai đoạn giữa trận / Mid-game), Agent sẽ tra cứu vào Bảng băm `tt` (Transposition Table).
*   Nếu Bảng băm có lưu kết quả phân tích nhánh này từ các turn trước, nó sẽ lấy `tt_hint_move` làm nước đi ưu tiên cao nhất để xét trước.

**Bước 5: Đào sâu lặp dần với Killer Moves & PVS (Iterative Deepening)**
*   Agent bắt đầu chạy vòng lặp độ sâu (Depth), tăng dần từ 0, 2, 4, 6... lên tối đa (24 hoặc 30).
*   Ở mỗi độ sâu, nó sắp xếp các nước đi ưu tiên: Nước gợi ý từ TT ở Bước 4 lên đầu, kế tiếp là nước từ bảng Killer Moves (các nước đi tốt từng gây cắt tỉa ở độ sâu tương ứng), sau đó đến các cột ở giữa bàn cờ (`[3, 2, 4, 1, 5, 0, 6]`).
*   Gọi hàm đệ quy `pvs()` (Principal Variation Search) với cửa sổ (alpha, beta).
    *   Trong `pvs()`, nó liên tục kiểm tra TT để tỉa nhánh.
    *   Dùng hàm heuristic để chấm điểm tại các lá cuối (leaf nodes).
*   Trong suốt quá trình này, một bộ đếm thời gian liên tục kiểm tra (`time.perf_counter() > deadline`). Nếu hết thời gian cho phép, quá trình tìm kiếm sẽ bị ngắt (TimeoutError) ngay lập tức.

**Bước 6: Trả về Kết quả & Lựa chọn kéo dài sự sống (Survival Delay)**
*   Sau khi bị ngắt bởi Timeout hoặc tìm thấy kết quả ở độ sâu tối đa, Agent lấy `best_move` của độ sâu hoàn chỉnh gần nhất.
*   Nếu Agent phát hiện mình ở thế cờ thua không thể cứu vãn (tất cả các nước đi đều có điểm số âm dạng `-999xx`), nó sẽ tự động chọn nước đi có số `ply` lớn nhất, tức là nước đi **kéo dài thời gian sống sót lâu nhất** trên bàn cờ thay vì tự hủy sớm.