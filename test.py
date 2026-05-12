from kaggle_environments import make
import webbrowser
import os
import Output.log_system as log_system
import Agents.FastAgent as FastAgent
import Agents.OpeningBook_optimized as OpeningBook_optimized
import Agents.ZobristHasingAgent as Zob
import SubmittedAgent.OpeningBook_optimized as Premium;

# Khởi tạo game log
log_system.init_game_log()

# tạo môi trường
env = make("connectx", debug=True)

# cho bot đánh nhau
# Agent đầu tiên: piece màu xanh có chữ K, đi trước
# Agent thứ 2: piece màu xám hình con vịt
env.run([Premium.agent, OpeningBook_optimized.agent])

# render HTML
html = env.render(mode="html")

# lưu file HTML
file_path = os.path.abspath("connectx.html")
with open(file_path, "w", encoding="utf-8") as f:
    f.write(html)

# mở trình duyệt
webbrowser.open("file://" + file_path)

# In tóm tắt game
log_system.print_game_summary()

print("Đã mở cửa sổ xem game!")

# zobrist thua bitboard