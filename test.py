from kaggle_environments import make
import webbrowser
import os
import MinimaxAgent
import test_agent

# tạo môi trường
env = make("connectx", debug=True)

# cho bot đánh nhau
env.run([test_agent.agent, "negamax"])

# render HTML
html = env.render(mode="html")

# lưu file
file_path = os.path.abspath("connectx.html")
with open(file_path, "w", encoding="utf-8") as f:
    f.write(html)

# mở trình duyệt
webbrowser.open("file://" + file_path)

print("Đã mở cửa sổ xem game!")