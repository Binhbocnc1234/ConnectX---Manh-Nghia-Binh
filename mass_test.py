from kaggle_environments import make
import numpy as np
import Agents.AlphaBetaAgent as AlphaBetaAgent
import Agents.MinimaxAgent as MinimaxAgent

def get_win_percentages(agent1, agent2, n_rounds=100):
    config = {'rows': 10, 'columns': 7, 'inarow': 4}
    outcomes = []

    for game_idx in range(n_rounds):
        env = make("connectx", configuration=config, debug=True)

        # Alternate starting player to keep evaluation fair.
        if game_idx % 2 == 0:
            agents = [agent1, agent2]
            first_name, second_name = "Agent 1", "Agent 2"
            swap_back = False
        else:
            agents = [agent2, agent1]
            first_name, second_name = "Agent 2", "Agent 1"
            swap_back = True

        env.run(agents)
        game_outcome = [player["reward"] for player in env.state]

        if swap_back:
            game_outcome = [game_outcome[1], game_outcome[0]]

        outcomes.append(game_outcome)

        final_board = np.asarray(env.state[0]["observation"]["board"])
        total_moves = int(np.count_nonzero(final_board))

        if game_outcome == [1, -1]:
            winner_text = "Agent 1 thắng"
        elif game_outcome == [-1, 1]:
            winner_text = "Agent 2 thắng"
        elif game_outcome == [0, 0]:
            winner_text = "Hòa"
        elif game_outcome == [None, 0]:
            winner_text = "Agent 1 thua do nước đi không hợp lệ"
        elif game_outcome == [0, None]:
            winner_text = "Agent 2 thua do nước đi không hợp lệ"
        else:
            winner_text = f"Kết quả đặc biệt: {game_outcome}"

        print(
            f"Game {game_idx + 1}/{n_rounds} | "
            f"Lượt đi trước: {first_name} | Lượt đi sau: {second_name} | "
            f"Tổng số nước đi: {total_moves} | Kết quả: {winner_text}"
        )

    print("Agent 1 Win Percentage:", np.round(outcomes.count([1, -1]) / len(outcomes), 2))
    print("Agent 2 Win Percentage:", np.round(outcomes.count([-1, 1]) / len(outcomes), 2))
    print("Number of Invalid Plays by Agent 1:", outcomes.count([None, 0]))
    print("Number of Invalid Plays by Agent 2:", outcomes.count([0, None]))

get_win_percentages(AlphaBetaAgent.agent, MinimaxAgent.agent, n_rounds=5)