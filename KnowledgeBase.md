# Kaggle ConnectX Minimax - Knowledge Base & Project Structure

Tài liệu này giải thích cấu trúc tổng thể của thư mục dự án, vai trò của từng file/thư mục, và tiến trình phát triển của các Agent (từ cơ bản đến nâng cao).

---

## 1. Thư mục gốc (Root Directory)
Đây là nơi chứa các script chạy môi trường (environment scripts) dùng để test, đánh giá và chơi với Agent.

*   **`test.py`**: Script chạy thử nghiệm môi trường Kaggle cơ bản. Cho phép cho 2 Agents đấu với nhau (ví dụ: `OpeningBook.agent` đấu với `ZobristHasingAgent.agent`) và render ra giao diện HTML để xem lại ván đấu.
*   **`vs_human_test.py`**: Script mở giao diện terminal để con người tự đánh với Agent. Dùng để test độ khó và xem cách Agent phòng thủ/tấn công.
*   **`mass_test.py`**: Script cho hàng loạt các Agent đấu với nhau nhiều ván (ví dụ: đánh 100 ván) để thống kê tỷ lệ Thắng/Thua/Hòa. Dùng để xếp hạng sức mạnh các Agent nội bộ.
*   **`log_system.py` & `game_log.json`**: Hệ thống logging dùng để theo dõi, đo đạc thời gian suy nghĩ (thinking time) của Agent ở từng lượt (ply). Rất quan trọng để tối ưu hóa, đảm bảo Agent không bị timeout (quá thời gian quy định của Kaggle).
*   **`KnowledgeBase.md`**: File tài liệu hiện tại, lưu trữ kiến thức và cấu trúc project.
*   **`README.md`**: File giới thiệu chung về project Kaggle ConnectX.

---

## 2. Thư mục `Agents/` (Khu vực cốt lõi)
Nơi chứa toàn bộ trí tuệ nhân tạo (AI) của project. Các Agent ở đây được phát triển từ phiên bản chậm, cơ bản nhất đến phiên bản được tối ưu hóa cực hạn.

### 2.1. Nền tảng (Foundations & Utilities)
*   **`foundation.py`**: Chứa các biến cấu hình và hằng số toàn cục. Nổi bật nhất là `MAX_THINK_TIME` (giới hạn thời gian suy nghĩ, ví dụ 1.2s - 10s tùy giai đoạn trận đấu), và các cấu hình bàn cờ.
*   **`heuristic.py`**: Chứa hàm `get_heuristic_bb` đóng vai trò là "con mắt" của AI. Đây là hàm chấm điểm bàn cờ (Board Evaluation), đánh giá độ mạnh yếu của các thế cờ dựa trên việc tạo ra các "cửa sổ" (windows) có tiềm năng thắng.
*   **`BuildBook.py`**: Script dùng để xây dựng Opening Book (Sách khai cuộc). Ban đầu nó dùng thuật toán BFS kết hợp Heuristic để tự tạo Book, nhưng hiện tại ta đã thay thế bằng dữ liệu xịn từ Pascal Pons.

### 2.2. Các Agents (Theo mức độ tiến hóa)
*   **`MinimaxAgent.py` & `AlphaBetaAgent.py`**: Thế hệ Agent đời đầu tiên. Dùng thuật toán Minimax truyền thống kết hợp cắt tỉa Alpha-Beta. Tuy nhiên, do viết bằng mảng 2D cơ bản của Python nên chạy khá chậm, chỉ search được nông.
*   **`BitboardAgent.py`**: Bản nâng cấp cấu trúc dữ liệu. Thay vì dùng mảng 2D, Agent chuyển sang dùng cấu trúc **Bitboard** (Dùng số nguyên 64-bit và các phép toán dịch bit/bitwise). Điều này giúp tốc độ tính toán tăng vọt.
*   **`PremiumAgent.py`**: Đây là một Agent giải pháp tham khảo được lấy từ trên GitHub, không nằm trong tiến trình phát triển chính của dự án chúng ta.
*   **`PrincipalVariationAgent(old).py`**: Áp dụng thuật toán **Principal Variation Search (PVS)** hay còn gọi là NegaScout. Thuật toán này tìm kiếm các nhánh cờ với "cửa sổ điểm" hẹp hơn (Null-Window Search) để cắt tỉa nhánh mạnh tay và tối ưu hơn so với Alpha-Beta truyền thống.
*   **`ZobristHasingAgent.py`**: Là bản nâng cấp trực tiếp của `PrincipalVariationAgent`. Agent này được tích hợp thêm **Transposition Table (Bảng băm)** thông qua thuật toán Zobrist Hashing. Kỹ thuật này giúp Agent "nhớ" được những thế cờ đã từng tính qua, kết hợp với PVS (giả định nước cờ lưu trong bảng băm là nước đi tốt nhất) để tăng tốc độ tìm kiếm lên cực hạn.
*   **`OpeningBook.py`**: Bản nâng cấp được tích hợp "Sách Khai Cuộc" tra cứu từ file `.jsonl` đến Ply 10.
*   **`OpeningBook_optimized.py`**: Phiên bản **Tối tân nhất và Hoàn hảo nhất hiện tại**. Khắc phục hoàn toàn các điểm yếu của bản cũ bằng cách:
    1.  **Quản lý thời gian linh hoạt (Dynamic Time Budgeting)**: Sử dụng tham số `remainingOverageTime` của Kaggle để tăng ngân sách thời gian suy nghĩ ở những nước then chốt (nhất là nước đi đầu tiên và khi bàn cờ phức tạp), tránh bị timeout vô lý.
    2.  **Bộ lọc Đe dọa / Nước đi Bắt buộc (Threat Detection & Forced-move Block)**: Trước khi tốn tài nguyên chạy PVS, Agent sẽ quét nhanh xem có cơ hội thắng ngay (Instant Win) hoặc đối thủ sắp thắng ở lượt tiếp theo để chặn đứng ngay lập tức (Forced-move Block).
    3.  **Lối chơi "Sống còn lâu nhất" (Defensive Survival Delay)**: Khi tất cả các nhánh đi đều dẫn đến thua cuộc, Agent thay vì tự hủy hay chọn bừa, nó sẽ chọn nước đi kéo dài sự sống lâu nhất (làm trì hoãn trận thua tối đa, tăng cơ hội đối phương đi sai).
    4.  **Tối ưu hóa thứ tự nước đi (Killer Moves Heuristic)**: Áp dụng bảng killer moves để ưu tiên các nước đi gây ra cắt tỉa alpha-beta mạnh mẽ, giúp search sâu hơn thêm 2-4 plies trong cùng khoảng thời gian.

### 2.3. Database Khai Cuộc
*   **`opening_book.jsonl`**: Đây là file cơ sở dữ liệu khổng lồ (khoảng 55MB) lưu trữ hơn 1 triệu thế cờ khai cuộc từ Ply 0 đến Ply 10. File này được trích xuất từ "Perfect Solver" của Pascal Pons. Nó là "vũ khí bí mật" giúp Agent đi cực kỳ hoàn hảo ở giai đoạn đầu trận.

---

## 3. Thư mục `Explanation/` (Tài liệu & Nghiên cứu)
Đây là khu vực "R&D" (Research & Development), chứa các tài nguyên, mã nguồn tham khảo và sổ tay Jupyter Notebook để đọc và hiểu về lý thuyết Connect 4.

*   **`PascalPon solution/`**: Thư mục chứa mã nguồn C++ của Pascal Pons (tác giả của Connect 4 Solver hoàn hảo nhất thế giới). Chúng ta đã viết thêm các công cụ C++ trong này:
    *   `export_book.cpp`: Dịch file binary nhị phân `7x6.book` thành file `opening_book.jsonl` đầy đủ.
    *   `export_book_pruned.cpp`: Phiên bản **nâng cấp có cắt tỉa**. Nó tự động bỏ qua việc mở rộng (expand) các nhánh cờ đã thắng/thua quá rõ ràng (abs(score) >= threshold), giúp người dùng dễ dàng build sách sâu hơn (Ply 12-14+) với bộ nhớ RAM cực thấp và file đầu ra siêu nhẹ!
*   **`Connect-Four-master/`**: Chứa một dự án nghiên cứu về Connect 4 dùng thuật toán học máy (TD-Learning / Reinforcement Learning) và mạng N-Tuple. Có các file weight `.agt` và `.txt`.
*   **`Agent-Explanation.ipynb` / `.html`**: Các sổ tay Jupyter diễn giải cách hoạt động của Minimax, Bitboard, và Heuristic một cách trực quan, có chứa các đồ thị phân tích.
*   **`GameRules.md`**: Tài liệu quy tắc chuẩn của Connect X / Connect 4.
*   **`hướng cải tiến.txt`**: File Text lưu lại những ý tưởng, phương án tối ưu Agent trong suốt quá trình trao đổi.

---

## 4. Các thư mục khác
*   **`Submissions/`**: Thư mục dùng để chứa các file Agent đã được đóng gói sẵn sàng đem nộp lên Kaggle (những file được nén thành `.tar.gz` hoặc `.py` bao gồm cả bộ thư viện).
*   **`Slides/`**: Chứa bài thuyết trình, báo cáo cho môn học hoặc cho dự án.

---

## 5. Luồng thực thi của Agent tối ưu nhất (`OpeningBook_optimized.py`)
Luồng thực thi của phiên bản tối ưu nhất được thiết kế để kết hợp sức mạnh tra cứu ngay lập tức (O(1)) của Opening Book và khả năng tìm kiếm sâu sắc của PVS.

Khi môi trường truyền trạng thái bàn cờ (`obs`) vào hàm `agent(obs, config)`, quy trình diễn ra như sau:

**Bước 1: Tính toán thời gian & Nạp Dữ liệu**
*   Xác định **Thinking Time Budget**: Nếu đây là lượt đầu tiên (Turn 1), Agent sẽ tận dụng triệt để `remainingOverageTime` (ví dụ lên đến 55 giây) để tính toán sâu sắc và xây dựng bảng băm cho các thế cờ tiếp theo. Với các nước đi sau, ngân sách được linh hoạt điều chỉnh xung quanh 1.85s đến 2.35s dựa vào lượng thời gian dự phòng còn dư.
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

---

## 6. Kaggle Submission & API Integration
Để quản lý việc nộp bài và tải trực tiếp các file log/replays của trận đấu từ Kaggle mà không cần tải thủ công, bạn có thể thiết lập như sau:

*   **API Token của bạn**: `KGAT_261d25f535aa7e4a17cc23e89bc86305`
*   **Cách sử dụng**: Cài đặt gói Kaggle trong môi trường:
    ```bash
    pip install kaggle
    ```
    Tạo thư mục `.kaggle` ở thư mục user cá nhân (ví dụ: `C:\Users\binhb\.kaggle\kaggle.json`) và điền thông tin xác thực Token của bạn để tự động hóa việc upload Agent cũng như fetch kết quả replay từ hệ thống về thư mục `Output/` của máy.

---

## 7. Hướng dẫn tự tạo Opening Book sâu hơn (Pruned Book Exporter)
Vì kích thước dữ liệu Opening Book đầy đủ tăng theo cấp số nhân, việc sử dụng phiên bản gốc sẽ làm tràn bộ nhớ (Out-Of-Memory) khi build đến Ply 12-14. Do đó bạn nên sử dụng `export_book_pruned.cpp` do chúng tôi cung cấp để tự xây dựng Opening Book tối ưu:

### Cách biên dịch & chạy:
1.  **Biên dịch**:
    ```bash
    g++ -O3 export_book_pruned.cpp -o export_book_pruned.exe
    ```
2.  **Cách chạy (Tự động loại bỏ các nhánh cờ dễ thắng/thua để tiết kiệm dung lượng)**:
    ```bash
    # Cú pháp: ./export_book_pruned.exe <đường_dẫn_7x6.book> [max_ply] [prune_threshold]
    ./export_book_pruned.exe ..\7x6.book 14 10 > e:\opening_book_pruned.jsonl
    ```
    *   `max_ply = 14`: Build sâu tới 14 nước đi khai cuộc (7 lượt mỗi bên).
    *   `prune_threshold = 10`: Nếu một vị trí có điểm số tuyệt đối từ 10 trở lên (thắng/thua quá rõ ràng), nhánh cờ đó sẽ không bị đào sâu nữa, giúp giảm kích thước file `.jsonl` đầu ra đến 80% mà không ảnh hưởng tới chất lượng khai cuộc!