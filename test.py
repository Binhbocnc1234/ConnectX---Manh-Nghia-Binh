from kaggle_environments import make
import webbrowser
import os
import log_system
import AlphaBetaAgent
import MinimaxAgent

# Khởi tạo game log
log_system.init_game_log()

# tạo môi trường
env = make("connectx", debug=True)

# cho bot đánh nhau
env.run([AlphaBetaAgent.agent, MinimaxAgent.agent])

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

