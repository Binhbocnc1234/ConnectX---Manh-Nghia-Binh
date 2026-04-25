from kaggle_environments import make
import numpy as np

import Agents.AlphaBetaAgent as AlphaBetaAgent


ROWS = 6
COLUMNS = 7
INAROW = 4
AGENT_FIRST = True


def render_board(board, rows=ROWS, columns=COLUMNS):
	grid = np.asarray(board).reshape(rows, columns)
	symbols = {0: ".", 1: "X", 2: "O"}
	print("\n  " + " ".join(str(c) for c in range(columns)))
	for row in grid:
		print(" |" + " ".join(symbols[int(cell)] for cell in row) + "|")
	print()


def valid_columns(board, columns=COLUMNS):
	return [c for c in range(columns) if board[c] == 0]


def board_move_count(board):
	return int(np.count_nonzero(np.asarray(board)))


def winner_text(reward_agent, reward_human):
	if reward_agent == 1 and reward_human == -1:
		return "Agent thắng"
	if reward_agent == -1 and reward_human == 1:
		return "Bạn thắng"
	if reward_agent == 0 and reward_human == 0:
		return "Hòa"
	if reward_agent is None or reward_human is None:
		return "Kết quả chưa xác định"
	return f"Kết quả đặc biệt: agent={reward_agent}, human={reward_human}"


def ask_human_move(observation):
	while True:
		render_board(observation.board)
		options = valid_columns(observation.board)
		print(f"Các cột hợp lệ: {options}")
		raw = input("Nhập cột bạn muốn đánh (0-6): ").strip()

		try:
			move = int(raw)
		except ValueError:
			print("Giá trị không hợp lệ. Hãy nhập số từ 0 đến 6.")
			continue

		if move not in range(COLUMNS):
			print("Cột ngoài phạm vi. Hãy nhập số từ 0 đến 6.")
			continue

		if move not in options:
			print("Cột này đã đầy. Hãy chọn cột khác.")
			continue

		return move


def agent_with_message(obs, config):
	move = AlphaBetaAgent.agent(obs, config)
	print(f"Agent chọn cột: {move}")
	return move


def main():
	env = make("connectx", debug=True)

	if AGENT_FIRST:
		agents = [agent_with_message, ask_human_move]
		print("Agent đi trước, bạn đi sau.")
	else:
		agents = [ask_human_move, agent_with_message]
		print("Bạn đi trước, agent đi sau.")

	env.run(agents)

	final_board = env.state[0]["observation"]["board"]
	reward_0 = env.state[0]["reward"]
	reward_1 = env.state[1]["reward"]
	total_moves = board_move_count(final_board)

	print("\nBàn cờ cuối cùng:")
	render_board(final_board)
	print(f"Tổng số nước đi: {total_moves}")
	print(f"Kết quả: {winner_text(reward_0, reward_1)}")


if __name__ == "__main__":
	main()
