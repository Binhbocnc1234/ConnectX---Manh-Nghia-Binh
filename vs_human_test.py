import numpy as np
from types import SimpleNamespace

import Agents.PrincipalVariationAgent as PrincipalAgent


ROWS = 6
COLUMNS = 7
INAROW = 4
AGENT_FIRST = False


def render_board(board, rows=ROWS, columns=COLUMNS):
	grid = np.asarray(board).reshape(rows, columns)
	symbols = {0: ".", 1: "X", 2: "O"}
	print("\n  " + " ".join(str(c) for c in range(columns)))
	for row in grid:
		print(" |" + " ".join(symbols[int(cell)] for cell in row) + "|")
	print()


def apply_move(board, column, mark, rows=ROWS, columns=COLUMNS):
	grid = np.asarray(board).reshape(rows, columns).copy()
	for row in range(rows - 1, -1, -1):
		if grid[row][column] == 0:
			grid[row][column] = mark
			break
	return grid.reshape(-1).tolist()


def valid_columns(board, columns=COLUMNS):
	return [c for c in range(columns) if board[c] == 0]


def board_move_count(board):
	return int(np.count_nonzero(np.asarray(board)))


def is_winning_board(board, mark, rows=ROWS, columns=COLUMNS, inarow=INAROW):
	grid = np.asarray(board).reshape(rows, columns)

	for row in range(rows):
		for col in range(columns - inarow + 1):
			if all(grid[row][col + i] == mark for i in range(inarow)):
				return True

	for row in range(rows - inarow + 1):
		for col in range(columns):
			if all(grid[row + i][col] == mark for i in range(inarow)):
				return True

	for row in range(rows - inarow + 1):
		for col in range(columns - inarow + 1):
			if all(grid[row + i][col + i] == mark for i in range(inarow)):
				return True

	for row in range(inarow - 1, rows):
		for col in range(columns - inarow + 1):
			if all(grid[row - i][col + i] == mark for i in range(inarow)):
				return True

	return False


def winner_text(winner_mark, agent_mark, human_mark):
	if winner_mark == agent_mark:
		return "Agent thắng"
	if winner_mark == human_mark:
		return "Bạn thắng"
	return "Hòa"


def ask_human_move(observation):
	while True:
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

		updated_board = apply_move(observation.board, move, observation.mark)
		print("Bàn cờ sau nước đi của bạn:")
		render_board(updated_board)

		return move


def agent_with_message(obs, config):
	move = PrincipalAgent.agent(obs, config)
	print(f"Agent chọn cột: {move}")
	return move


def main():
	board = [0] * (ROWS * COLUMNS)
	config = SimpleNamespace(rows=ROWS, columns=COLUMNS, inarow=INAROW)
	agent_mark = 1 if AGENT_FIRST else 2
	human_mark = 2 if AGENT_FIRST else 1
	current_mark = 1
	winner_mark = None

	if AGENT_FIRST:
		print("Agent đi trước, bạn đi sau.")
	else:
		print("Bạn đi trước, agent đi sau.")

	while True:
		if current_mark == agent_mark:
			obs = SimpleNamespace(board=board, mark=agent_mark)
			move = agent_with_message(obs, config)

			if move not in range(COLUMNS) or move not in valid_columns(board):
				print("Agent đi lỗi (cột ngoài phạm vi hoặc cột đầy). Bạn thắng theo luật.")
				winner_mark = human_mark
				break

			board = apply_move(board, move, agent_mark)
			print("Bàn cờ sau nước đi của agent:")
			render_board(board)
		else:
			obs = SimpleNamespace(board=board, mark=human_mark)
			move = ask_human_move(obs)
			board = apply_move(board, move, human_mark)

		if is_winning_board(board, current_mark):
			winner_mark = current_mark
			break

		if not valid_columns(board):
			break

		current_mark = 2 if current_mark == 1 else 1

	total_moves = board_move_count(board)

	print("\nBàn cờ cuối cùng:")
	render_board(board)
	print(f"Tổng số nước đi: {total_moves}")
	print(f"Kết quả: {winner_text(winner_mark, agent_mark, human_mark)}")


if __name__ == "__main__":
	main()
