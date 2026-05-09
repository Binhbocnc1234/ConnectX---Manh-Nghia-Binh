import Output.log_system as log_system
from kaggle_environments import make
import argparse
import numpy as np
import Agents.AlphaBetaAgent as AlphaBetaAgent
import Agents.BitboardAgent as BitBoardAgent
import Agents.ZobristHasingAgent as Principal
import Agents.OpeningBook_optimized as OpeningBookOpt
import Agents.OpeningBook as OpeningBook
import Agents.foundation as foundation


def is_early_loss(game_outcome, total_moves, move_limit=30):
    if total_moves >= move_limit:
        return False

    return game_outcome in ([1, -1], [-1, 1], [None, 0], [0, None])


def get_win_percentages(agent1, agent2, n_rounds=10):
    config = {'rows': 6, 'columns': 7, 'inarow': 4}
    outcomes = []
    
    for game_idx in range(n_rounds):
        # Dynamically vary thinking time from 0.5 to 2.0
        if n_rounds > 1:
            think_time = round(0.5 + (2.0 - 0.5) * (game_idx / (n_rounds - 1)), 2)
        else:
            think_time = 0.5
        
        # Wrap agents to pass the dynamically calculated timeout
        a1 = lambda obs, config: agent1(obs, config, timeout=think_time)
        a2 = lambda obs, config: agent2(obs, config, timeout=think_time)
        
        log_system.init_game_log()
        env = make("connectx", configuration=config, debug=True)
        
        # Alternate starting player
        if game_idx % 2 == 0:
            agents = [a1, a2]
            first_name, second_name = "Agent 1", "Agent 2"
            swap_back = False
        else:
            agents = [a2, a1]
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
            winner_text = "Agent 1 thua (Invalid)"
        elif game_outcome == [0, None]:
            winner_text = "Agent 2 thua (Invalid)"
        else:
            winner_text = f"Kết quả: {game_outcome}"

        print(
            f"Round {game_idx + 1}/{n_rounds} | Time: {think_time}s | "
            f"1st: {first_name} | Result: {winner_text} | Moves: {total_moves}"
        )

        # if is_early_loss(game_outcome, total_moves):
        #     print(f"Lỗi: ván {game_idx + 1} kết thúc sớm ({total_moves} nước). Check game_log.json")
        #     break

    print("\n" + "="*40)
    print("FINAL SUMMARY")
    print("="*40)
    print("Agent 1 Win %:", np.round(outcomes.count([1, -1]) / len(outcomes), 2))
    print("Agent 2 Win %:", np.round(outcomes.count([-1, 1]) / len(outcomes), 2))
    print("Draw %:", np.round(outcomes.count([0, 0]) / len(outcomes), 2))


def parse_args():
    parser = argparse.ArgumentParser(description="Run repeated ConnectX matches for agent evaluation.")
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of games to run (default: 10).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    # Test OpeningBook_optimized vs itself
    get_win_percentages(OpeningBookOpt.agent, OpeningBook.agent, n_rounds=args.rounds)


if __name__ == "__main__":
    main()