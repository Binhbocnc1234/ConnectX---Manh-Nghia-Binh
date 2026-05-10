try:
    import Output.log_system as log_system
except Exception:
    log_system = None

from Agents.engine_bridge import run_opening_book_opt


def agent(obs, config, timeout=2):
    return run_opening_book_opt(obs, config, timeout=timeout)


def _log_move(move, start_time):
    pass
