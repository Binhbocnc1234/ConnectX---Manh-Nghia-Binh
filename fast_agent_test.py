import time
import Agents.FastAgent as FastAgent
class Obs: pass
class Conf: pass

obs = Obs()
obs.board = [0]*42
obs.mark = 1
obs.step = 0
obs.remainingOverageTime = 60.0

conf = Conf()
conf.columns = 7
conf.timeout = 2.0

t0 = time.perf_counter()
try:
    move = FastAgent.run_opening_book_opt(obs, conf, timeout=2.0)
    print("move:", move)
except Exception as e:
    print("exception:", e)
t1 = time.perf_counter()
print("elapsed:", t1-t0, "s")