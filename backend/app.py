import json
import random
import re
import time
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set
import pathlib

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = pathlib.Path(__file__).parent / "raw_questions.txt"

def parse_questions():
    """Парсит текстовый файл в список вопросов."""
    if not DATA_PATH.exists():
        return []
    
    raw = DATA_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"\bANSWER:", raw)
    questions = []
    
    for i in range(len(blocks) - 1):
        block_lines = [line.strip() for line in blocks[i].split("\n")]
        answer_raw = blocks[i + 1].strip().split("\n")[0].strip().upper()
        
        question_text = ""
        choices = []
        
        for line in block_lines:
            if not line:
                continue
            if re.match(r"^[A-E]\)", line):
                choices.append(line)
                continue
            if len(line) == 1 and line.upper() in "ABCDE":
                continue
            if question_text == "":
                question_text = line
        
        if question_text and choices:
            questions.append({
                "question": question_text,
                "choices": choices,
                "answer": answer_raw
            })
    
    return questions

QUESTIONS = parse_questions()

# Хранилище игроков и активных сессий
players: Dict[str, dict] = {}
active_connections: Set[WebSocket] = set()

async def broadcast_leaderboard():
    """Отправляет обновленный рейтинг всем подключенным игрокам."""
    board = sorted(
        players.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )[:10]  # Топ-10
    
    leaderboard_data = {
        "type": "leaderboard",
        "players": [
            {"name": name, "score": data["score"]}
            for name, data in board
        ]
    }
    
    for connection in active_connections:
        try:
            await connection.send_json(leaderboard_data)
        except:
            pass

@app.get("/")
async def root():
    return {
        "status": "Sprint Quiz Backend Running",
        "questions_loaded": len(QUESTIONS),
        "active_players": len(players)
    }

@app.get("/stats")
async def stats():
    return {
        "total_questions": len(QUESTIONS),
        "active_players": len(players),
        "leaderboard": sorted(
            [{"name": k, "score": v["score"]} for k, v in players.items()],
            key=lambda x: x["score"],
            reverse=True
        )[:10]
    }

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.add(ws)
    player_id = None
    
    try:
        while True:
            data = await ws.receive_json()
            
            # Регистрация игрока
            if data["action"] == "register":
                player_id = data["name"]
                players[player_id] = {
                    "score": 0,
                    "start_time": time.time(),
                    "game_active": True
                }
                await ws.send_json({
                    "status": "registered",
                    "name": player_id,
                    "total_questions": len(QUESTIONS)
                })
                await broadcast_leaderboard()
            
            # Старт игры (60 секунд)
            elif data["action"] == "start_game":
                if player_id:
                    players[player_id]["start_time"] = time.time()
                    players[player_id]["game_active"] = True
                    players[player_id]["score"] = 0
                    await ws.send_json({"status": "game_started"})
            
            # Запрос нового вопроса
            elif data["action"] == "get_question":
                if not QUESTIONS:
                    await ws.send_json({"error": "No questions available"})
                    continue
                
                q = random.choice(QUESTIONS)
                await ws.send_json({
                    "type": "question",
                    "q": q
                })
            
            # Ответ на вопрос
            elif data["action"] == "answer":
                if not player_id or player_id not in players:
                    continue
                
                # Проверка времени (60 секунд)
                elapsed = time.time() - players[player_id]["start_time"]
                if elapsed > 60:
                    players[player_id]["game_active"] = False
                    await ws.send_json({
                        "type": "game_over",
                        "final_score": players[player_id]["score"],
                        "time": 60
                    })
                    await broadcast_leaderboard()
                    continue
                
                answer = data["answer"].upper()
                correct = data["correct"].upper()
                
                if answer == correct:
                    players[player_id]["score"] += 1
                    result = "correct"
                else:
                    result = "wrong"
                
                await ws.send_json({
                    "type": "answer_result",
                    "result": result,
                    "score": players[player_id]["score"],
                    "time_left": max(0, 60 - elapsed)
                })
                
                # Обновляем рейтинг для всех
                await broadcast_leaderboard()
            
            # Запрос рейтинга
            elif data["action"] == "get_leaderboard":
                await broadcast_leaderboard()
    
    except WebSocketDisconnect:
        active_connections.discard(ws)
        # Не удаляем игрока, чтобы сохранить его в рейтинге
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        active_connections.discard(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)