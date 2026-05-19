#!/usr/bin/env python3
"""
get_bad_matches.py

Fetch replays/logs from a Kaggle submission or analyze local Output/ replay files,
then extract matches that are "bad" for debugging.

Bad match criteria (heuristic):
 - Our agent lost and the match ended before `max_moves` (default 35), OR
 - Our agent played first but the match ended in a draw or loss.

Usage examples:
  # Analyze local Output/ folder
  python Debug/get_bad_matches.py --input-dir Output --out bad_matches

  # If Kaggle API is configured, try to download submission artifacts (best-effort)
  python Debug/get_bad_matches.py --submission SUBMISSION_ID --competition COMP_NAME --out bad_matches

Notes:
 - This script uses simple heuristics to infer winner / moves from replay JSON and agent logs.
 - It supports direct local inspection (recommended). If you want automatic Kaggle download,
   ensure the `kaggle` package is installed and configured (or edit the script to inject credentials).
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
from glob import glob
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List


MAX_DEFAULT_MOVES = 35


def read_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_id_from_episode(path: str) -> str:
    # episode-76374283.json -> 76374283
    m = re.search(r'episode[-_]?([0-9]+)\.json$', path)
    if m:
        return m.group(1)
    # fallback: filename digits
    m = re.search(r'([0-9]+)', os.path.basename(path))
    return m.group(1) if m else os.path.splitext(os.path.basename(path))[0]


def flatten_stdout_from_log(log_json: Any) -> str:
    # Kaggle agent logs often are nested lists; find all strings under 'stdout' keys
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'stdout' and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for item in o:
                walk(item)

    walk(log_json)
    return "\n".join(out)


def detect_moves_from_log(flat_stdout: str) -> int:
    # look for lines like "[OpeningBookOpt] Start turn 0" and take max turn
    turns = [int(m) for m in re.findall(r'Start turn\s*(\d+)', flat_stdout)]
    if turns:
        max_turn = max(turns)
        # If turns are 0,2,4,... then number of plies = max_turn + 1
        return max_turn + 1
    # fallback: count occurrences of "Start turn" as moves
    cnt = flat_stdout.count('Start turn')
    if cnt:
        return cnt
    # fallback: try to find number of "At depth" prints as heuristic
    return flat_stdout.count('At depth:')


def detect_outcome_from_episode(ep_json: Any, agent_log_stdout: str) -> Dict[str, Any]:
    # Try several heuristics to determine if agent won/lost/draw and whether agent was first
    result = {'outcome': 'unknown', 'agent_first': None, 'reason': ''}

    # 1) If episode contains explicit rewards
    def find_numbers(obj):
        found = []
        if isinstance(obj, dict):
            for v in obj.values():
                found.extend(find_numbers(v))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(find_numbers(item))
        elif isinstance(obj, (int, float)):
            found.append(obj)
        return found

    nums = find_numbers(ep_json)
    # Heuristic: if last numbers include -1/0/1 consider them as rewards
    for n in reversed(nums[-10:]):
        if n in (1, -1, 0):
            # treat as final reward for this agent
            if n == 1:
                result['outcome'] = 'win'
            elif n == -1:
                result['outcome'] = 'loss'
            else:
                result['outcome'] = 'draw'
            result['reason'] = 'found numeric reward in episode'
            break

    # 2) If still unknown, parse agent log for common phrases
    if result['outcome'] == 'unknown':
        s = agent_log_stdout.lower()
        if re.search(r"\bwon\b|\bwin\b|\bcongratulations\b", s):
            result['outcome'] = 'win'
            result['reason'] = 'log contains win phrase'
        elif re.search(r"\blost\b|\blose\b|\bdefeat\b", s):
            result['outcome'] = 'loss'
            result['reason'] = 'log contains loss phrase'
        elif re.search(r"\bdraw\b|\btie\b|\bdrawn\b|\bdraws\b", s):
            result['outcome'] = 'draw'
            result['reason'] = 'log contains draw phrase'

    # 3) Determine if agent was first: if log contains "Start turn 0" it's player who moves at step 0
    if re.search(r'Start turn\s*0', agent_log_stdout):
        result['agent_first'] = True
    else:
        # If log includes odd start turn numbers only, assume second
        if re.search(r'Start turn\s*1', agent_log_stdout):
            result['agent_first'] = False

    return result


def find_episode_and_logs(input_dir: str) -> List[Dict[str, str]]:
    # Find episode-*.json and <id>-*.json log files and pair by id
    episodes = glob(os.path.join(input_dir, 'episode-*.json'))
    pairs = []
    for ep in episodes:
        eid = extract_id_from_episode(ep)
        # look for any log starting with eid-*.json
        logs = glob(os.path.join(input_dir, f'{eid}-*.json'))
        pairs.append({'id': eid, 'episode': ep, 'logs': logs})
    return pairs


def analyze_local(input_dir: str, out_dir: str, max_moves: int = MAX_DEFAULT_MOVES) -> List[Dict[str, Any]]:
    os.makedirs(out_dir, exist_ok=True)
    pairs = find_episode_and_logs(input_dir)
    badMatches = []

    for p in pairs:
        eid = p['id']
        ep_path = p['episode']
        logs = p['logs']
        if not logs:
            print(f"Skipping {eid}: no agent log found")
            continue

        # pick the first log file (our agent's log)
        log_path = logs[0]
        try:
            ep_json = read_json(ep_path)
        except Exception as e:
            print(f"Failed to read episode {ep_path}: {e}")
            continue
        try:
            log_json = read_json(log_path)
        except Exception as e:
            print(f"Failed to read log {log_path}: {e}")
            log_json = None

        stdout_flat = flatten_stdout_from_log(log_json) if log_json is not None else ''
        moves = detect_moves_from_log(stdout_flat)
        outcome = detect_outcome_from_episode(ep_json, stdout_flat)

        is_bad = False
        reasons = []
        if outcome['outcome'] == 'loss' and moves < max_moves:
            is_bad = True
            reasons.append(f"lost in {moves} moves (<{max_moves})")
        if outcome['agent_first'] is True and outcome['outcome'] in ('loss', 'draw'):
            is_bad = True
            reasons.append(f"went first but {outcome['outcome']}")

        if is_bad:
            out_record = {
                'id': eid,
                'episode': ep_path,
                'log': log_path,
                'moves': moves,
                'outcome': outcome,
                'reasons': reasons,
            }
            badMatches.append(out_record)
            # copy files to out_dir for inspection
            base = os.path.join(out_dir, f"{eid}")
            os.makedirs(base, exist_ok=True)
            shutil.copy2(ep_path, os.path.join(base, os.path.basename(ep_path)))
            shutil.copy2(log_path, os.path.join(base, os.path.basename(log_path)))

    # write summary
    summary_path = os.path.join(out_dir, 'bad_matches_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(badMatches, f, indent=2)
    return badMatches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=str, default='Output', help='Local folder containing episode-*.json and <id>-*.json logs')
    parser.add_argument('--out', type=str, default='Output/bad_matches', help='Directory to write bad matches')
    parser.add_argument('--max-moves', type=int, default=MAX_DEFAULT_MOVES, help='Max moves threshold for early loss')
    parser.add_argument('--submission', type=str, default=None, help='Kaggle submission id to download artifacts from')
    parser.add_argument('--competition', type=str, default=None, help='Kaggle competition name (required with --submission)')
    args = parser.parse_args()
    # If submission provided, attempt to download artifacts into a temp folder
    work_input = args.input_dir
    temp_dir = None
    if args.submission:
        if not args.competition:
            print('When using --submission you must also provide --competition')
            return
        try:
            temp_dir = tempfile.mkdtemp(prefix='kaggle_sub_')
            print(f'Downloading submission {args.submission} (competition {args.competition}) into {temp_dir}')
            fetched = fetch_submission_artifacts(args.submission, args.competition, temp_dir)
            if not fetched:
                print('Failed to fetch submission artifacts; falling back to local input-dir')
            else:
                work_input = temp_dir
        except Exception as e:
            print('Error while fetching submission:', e)

    bad = analyze_local(work_input, args.out, max_moves=args.max_moves)
    print(f"Found {len(bad)} bad matches. Summary written to {args.out}/bad_matches_summary.json")


def _read_kb_token(kb_path: str) -> str | None:
    try:
        text = read_json(kb_path) if kb_path.endswith('.json') else open(kb_path, 'r', encoding='utf-8').read()
    except Exception:
        return None
    m = re.search(r'KGAT_[0-9a-fA-F]{20,}', text)
    if m:
        return m.group(0)
    return None


def _write_kaggle_json(token: str) -> Path:
    # Best-effort: write ~/.kaggle/kaggle.json with token as key and fallback username
    home = Path.home()
    kaggle_dir = home / '.kaggle'
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    username = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
    kaggle_json = kaggle_dir / 'kaggle.json'
    data = {'username': username, 'key': token}
    with open(kaggle_json, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    try:
        os.chmod(kaggle_json, 0o600)
    except Exception:
        pass
    return kaggle_json


def fetch_submission_artifacts(submission_id: str, competition: str, dest_dir: str) -> bool:
    """Attempt to fetch submission artifacts into dest_dir.
    Returns True on success, False otherwise.
    """
    # 1) Try to read token from Documentation/KnowledgeBase.md
    kb = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Documentation', 'KnowledgeBase.md')
    if not os.path.exists(kb):
        # also try repo Documentation folder
        kb = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Documentation', 'KnowledgeBase.md')
    token = None
    if os.path.exists(kb):
        token = _read_kb_token(kb)
    if token:
        _write_kaggle_json(token)

    # 2) Try kaggle CLI (best-effort)
    try:
        cmd = ['kaggle', 'competitions', 'submissions', 'download', '-c', competition, '-s', submission_id, '-p', dest_dir, '--unzip']
        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if res.returncode == 0:
            return True
        # Some CLI versions may not support -s; try using -m (submission file number)
        cmd2 = ['kaggle', 'competitions', 'submissions', 'download', '-c', competition, '-m', submission_id, '-p', dest_dir, '--unzip']
        res2 = subprocess.run(cmd2, check=False, capture_output=True, text=True)
        if res2.returncode == 0:
            return True
        print('kaggle CLI download failed:', res.stdout + '\n' + res.stderr)
    except FileNotFoundError:
        print('kaggle CLI not found; try `pip install kaggle`')
    except Exception as e:
        print('kaggle CLI error:', e)

    # 3) Try Python Kaggle API if installed
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        # download submissions for competition; attempt to download by submission id
        # The API provides competition_submissions_list and competition_submissions_download methods
        try:
            api.competition_submissions_download(competition, submission_id, path=dest_dir, unzip=True)
            return True
        except Exception:
            # fallback: list all and try to find file
            subs = api.competition_submissions_list(competition)
            for s in subs:
                if submission_id in str(s):
                    # attempt download by file name
                    try:
                        api.competition_submissions_download(competition, s, path=dest_dir, unzip=True)
                        return True
                    except Exception:
                        continue
    except Exception:
        pass

    return False


if __name__ == '__main__':
    main()
