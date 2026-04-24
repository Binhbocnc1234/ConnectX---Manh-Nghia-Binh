"""
Log System - Quản lý lưu trữ dữ liệu game
==========================================
Cung cấp các hàm để:
- Khởi tạo file JSON trước game
- Ghi dữ liệu move vào file JSON sau mỗi nước đi
"""

import json
import os
from datetime import datetime

LOG_FILE = "game_log.json"
ENABLED = True

def init_game_log():
    
    """
    Khởi tạo file game_log.json mới cho một trận game.
    
    Ý nghĩa:
    - Clear log cũ nếu có
    - Tạo cấu trúc JSON cơ bản
    - Thêm timestamp và metadata
    """
    if (ENABLED == False):
        return
    game_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "game": "ConnectX",
            "config": {
                "rows": 6,
                "columns": 7,
                "inarow": 4
            }
        },
        "moves": [],
        "statistics": {
            "total_moves": 0,
            "agents": {}
        }
    }
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(game_data, f, indent=2, ensure_ascii=False)


def log_move(agent_name, move, think_time):
    """
    Ghi một nước đi vào file JSON.
    
    Ý nghĩa:
    - Append move vào danh sách moves
    - Update thống kê agent
    - Tự động update total_moves
    
    Tham số:
    - agent_name: Tên agent ("AlphaBetaAgent" hoặc "MinimaxAgent")
    - move: Cột được chọn (0-6)
    - think_time: Thời gian suy nghĩ (giây)
    """
    if (ENABLED == False):
        return
    try:
        # Read file hiện tại
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            game_data = json.load(f)
        
        # Thêm move mới
        move_number = len(game_data["moves"])
        new_move = {
            "move_number": move_number,
            "agent": agent_name,
            "move": int(move),
            "think_time": round(think_time, 4),
            "timestamp": datetime.now().isoformat()
        }
        game_data["moves"].append(new_move)
        
        # Update statistics
        game_data["statistics"]["total_moves"] = move_number + 1
        
        if agent_name not in game_data["statistics"]["agents"]:
            game_data["statistics"]["agents"][agent_name] = {
                "total_moves": 0,
                "total_think_time": 0,
                "avg_think_time": 0
            }
        
        agent_stats = game_data["statistics"]["agents"][agent_name]
        agent_stats["total_moves"] += 1
        agent_stats["total_think_time"] = round(agent_stats["total_think_time"] + think_time, 4)
        agent_stats["avg_think_time"] = round(agent_stats["total_think_time"] / agent_stats["total_moves"], 4)
        
        # Write file
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(game_data, f, indent=2, ensure_ascii=False)
    
    except Exception as e:
        print(f"❌ Error logging move: {e}")


def print_game_summary():
    """
    In ra màn hình tóm tắt game từ file JSON.
    """
    if (ENABLED == False):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            game_data = json.load(f)
        
        print("\n" + "=" * 80)
        print("🎮 GAME RESULT")
        print("=" * 80)
        
        # Print moves log
        moves = game_data.get("moves", [])
        if moves:
            print("\n📊 MOVES LOG:")
            print("-" * 80)
            for move in moves:
                move_num = move["move_number"] + 1
                agent_name = move["agent"]
                move_col = move["move"]
                think_time = move["think_time"]
                print(f"Move {move_num}: {agent_name} played column {move_col} (⏱ {think_time}s)")
            
            print("-" * 80)
            
            # Print statistics
            stats = game_data.get("statistics", {})
            print(f"\n📈 STATISTICS:")
            print(f"Total moves: {stats.get('total_moves', 0)}")
            
            for agent_name, agent_stats in stats.get("agents", {}).items():
                print(f"\n  {agent_name}:")
                print(f"    - Total moves: {agent_stats['total_moves']}")
                print(f"    - Avg think time: {agent_stats['avg_think_time']}s")
                print(f"    - Total think time: {agent_stats['total_think_time']}s")
        
        print("=" * 80)
        print(f"✅ Game log saved to: {os.path.abspath(LOG_FILE)}")
        
    except Exception as e:
        print(f"❌ Error reading game summary: {e}")
