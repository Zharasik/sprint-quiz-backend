import json
import random
import re
import time
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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

DATA_PATH = pathlib.Path(__file__).parent / "midterm.txt"

def parse_questions():
    """Парсит текстовый файл в список вопросов."""
    if not DATA_PATH.exists():
        print(f"ERROR: File {DATA_PATH} not found!")
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
    
    print(f"INFO: Loaded {len(questions)} questions from {DATA_PATH}")
    return questions

QUESTIONS = parse_questions()

players: Dict[str, dict] = {}
active_connections: Set[WebSocket] = set()

async def broadcast_leaderboard():
    """Отправляет обновленный рейтинг всем подключенным игрокам."""
    board = sorted(
        players.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )[:10]
    
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

# HTML Frontend встроенный
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sprint Quiz - Соревновательная подготовка</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
    <div id="root"></div>
    
    <script type="text/babel">
        const { useState, useEffect, useRef } = React;
        
        // Lucide icons (простые SVG)
        const Trophy = () => (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path>
                <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path>
                <path d="M4 22h16"></path>
                <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"></path>
                <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"></path>
                <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"></path>
            </svg>
        );
        
        const Clock = () => (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
        );
        
        const Users = () => (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
        );
        
        const Play = () => (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
        );
        
        const Home = () => (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
        );
        
        function SprintQuiz() {
            const [ws, setWs] = useState(null);
            const [screen, setScreen] = useState('home');
            const [playerName, setPlayerName] = useState('');
            const [currentQuestion, setCurrentQuestion] = useState(null);
            const [score, setScore] = useState(0);
            const [timeLeft, setTimeLeft] = useState(60);
            const [leaderboard, setLeaderboard] = useState([]);
            const [feedback, setFeedback] = useState(null);
            const [connectionStatus, setConnectionStatus] = useState('disconnected');
            const timerRef = useRef(null);
            const wsRef = useRef(null);
            
            const WS_URL = `ws${window.location.protocol === 'https:' ? 's' : ''}://${window.location.host}/ws`;
            
            useEffect(() => {
                return () => {
                    if (wsRef.current) {
                        wsRef.current.close();
                    }
                    if (timerRef.current) {
                        clearInterval(timerRef.current);
                    }
                };
            }, []);
            
            const connectWebSocket = () => {
                console.log('Connecting to:', WS_URL);
                const socket = new WebSocket(WS_URL);
                wsRef.current = socket;
                
                socket.onopen = () => {
                    console.log('✅ WebSocket подключен');
                    setConnectionStatus('connected');
                    setWs(socket);
                    
                    // Сразу регистрируем игрока
                    console.log('Registering player:', playerName);
                    socket.send(JSON.stringify({
                        action: 'register',
                        name: playerName
                    }));
                };
                
                socket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);
                    
                    if (data.status === 'registered') {
                        console.log('✅ Player registered, starting game...');
                        setConnectionStatus('registered');
                        
                        // Начинаем игру
                        socket.send(JSON.stringify({ action: 'start_game' }));
                        
                        // Запрашиваем первый вопрос
                        setTimeout(() => {
                            console.log('Requesting first question...');
                            socket.send(JSON.stringify({ action: 'get_question' }));
                        }, 200);
                        
                        setScreen('game');
                        setScore(0);
                        setTimeLeft(60);
                        startTimer();
                    }
                    
                    if (data.type === 'question') {
                        console.log('✅ Question received:', data.q.question);
                        setCurrentQuestion(data.q);
                        setFeedback(null);
                    }
                    
                    if (data.type === 'answer_result') {
                        console.log('Answer result:', data.result);
                        setScore(data.score);
                        setFeedback(data.result);
                        
                        setTimeout(() => {
                            setFeedback(null);
                            console.log('Requesting next question...');
                            socket.send(JSON.stringify({ action: 'get_question' }));
                        }, 800);
                    }
                    
                    if (data.type === 'leaderboard') {
                        console.log('Leaderboard updated:', data.players);
                        setLeaderboard(data.players);
                    }
                    
                    if (data.type === 'game_over') {
                        console.log('Game over!');
                        endGame(data.final_score);
                    }
                };
                
                socket.onerror = (error) => {
                    console.error('❌ WebSocket ошибка:', error);
                    setConnectionStatus('error');
                };
                
                socket.onclose = () => {
                    console.log('WebSocket отключен');
                    setConnectionStatus('disconnected');
                };
            };
            
            const startGame = () => {
                if (!playerName.trim()) {
                    alert('Введите ваше имя!');
                    return;
                }
                
                console.log('Starting game for:', playerName);
                setConnectionStatus('connecting');
                connectWebSocket();
            };
            
            const startTimer = () => {
                if (timerRef.current) {
                    clearInterval(timerRef.current);
                }
                
                timerRef.current = setInterval(() => {
                    setTimeLeft((prev) => {
                        if (prev <= 1) {
                            endGame(score);
                            return 0;
                        }
                        return prev - 1;
                    });
                }, 1000);
            };
            
            const endGame = (finalScore) => {
                console.log('Ending game with score:', finalScore);
                if (timerRef.current) {
                    clearInterval(timerRef.current);
                }
                setScore(finalScore);
                setScreen('leaderboard');
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({ action: 'get_leaderboard' }));
                }
            };
            
            const handleAnswer = (choice) => {
                if (!currentQuestion || feedback) return;
                
                const answer = choice.charAt(0);
                console.log('Answering:', answer, 'Correct:', currentQuestion.answer);
                
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({
                        action: 'answer',
                        answer: answer,
                        correct: currentQuestion.answer
                    }));
                }
            };
            
            const restartGame = () => {
                setScreen('home');
                setScore(0);
                setTimeLeft(60);
                setCurrentQuestion(null);
                setFeedback(null);
                setPlayerName('');
                setConnectionStatus('disconnected');
                if (wsRef.current) {
                    wsRef.current.close();
                }
            };
            
            if (screen === 'home') {
                return (
                    <div className="min-h-screen bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center p-4">
                        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full">
                            <div className="text-center mb-8">
                                <div className="inline-flex bg-gradient-to-r from-yellow-400 to-orange-500 p-4 rounded-full mb-4">
                                    <Trophy />
                                </div>
                                <h1 className="text-4xl font-bold text-gray-800 mb-2">Sprint Quiz</h1>
                                <p className="text-gray-600">60 секунд. Максимум правильных ответов.</p>
                                {connectionStatus !== 'disconnected' && (
                                    <p className="text-sm text-blue-600 mt-2">
                                        {connectionStatus === 'connecting' && '🔄 Подключение...'}
                                        {connectionStatus === 'connected' && '✅ Подключено!'}
                                        {connectionStatus === 'registered' && '✅ Игра началась!'}
                                        {connectionStatus === 'error' && '❌ Ошибка подключения'}
                                    </p>
                                )}
                            </div>
                            
                            <div className="space-y-4">
                                <input
                                    type="text"
                                    placeholder="Введите ваше имя"
                                    value={playerName}
                                    onChange={(e) => setPlayerName(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && startGame()}
                                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:border-blue-500 focus:outline-none text-lg"
                                    disabled={connectionStatus === 'connecting'}
                                />
                                
                                <button
                                    onClick={startGame}
                                    disabled={!playerName.trim() || connectionStatus === 'connecting'}
                                    className="w-full bg-gradient-to-r from-green-400 to-blue-500 text-white py-4 rounded-xl font-bold text-lg hover:shadow-lg transform hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    <Play />
                                    {connectionStatus === 'connecting' ? 'Подключение...' : 'Начать игру'}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            }
            
            if (screen === 'game') {
                return (
                    <div className="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-4">
                        <div className="max-w-4xl mx-auto">
                            <div className="bg-white rounded-2xl shadow-lg p-4 mb-4 flex justify-between items-center">
                                <div className="flex items-center gap-4">
                                    <div className="bg-blue-100 p-3 rounded-xl">
                                        <Users />
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-500">Игрок</p>
                                        <p className="font-bold text-lg">{playerName}</p>
                                    </div>
                                </div>
                                
                                <div className="flex items-center gap-6">
                                    <div className="text-center">
                                        <p className="text-sm text-gray-500">Счёт</p>
                                        <p className="text-2xl font-bold text-green-600">{score}</p>
                                    </div>
                                    
                                    <div className="flex items-center gap-2 bg-red-100 px-4 py-2 rounded-xl">
                                        <Clock />
                                        <span className="text-2xl font-bold text-red-600">{timeLeft}s</span>
                                    </div>
                                </div>
                            </div>
                            
                            {!currentQuestion ? (
                                <div className="bg-white rounded-2xl shadow-2xl p-8 text-center">
                                    <div className="animate-pulse">
                                        <p className="text-xl text-gray-600">Загрузка вопроса...</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white rounded-2xl shadow-2xl p-8">
                                    <h2 className="text-2xl font-bold text-gray-800 mb-6">
                                        {currentQuestion.question}
                                    </h2>
                                    
                                    <div className="space-y-3">
                                        {currentQuestion.choices.map((choice, idx) => {
                                            const isCorrect = feedback === 'correct' && choice.charAt(0) === currentQuestion.answer;
                                            const isWrong = feedback === 'wrong' && choice.charAt(0) !== currentQuestion.answer;
                                            
                                            return (
                                                <button
                                                    key={idx}
                                                    onClick={() => handleAnswer(choice)}
                                                    disabled={feedback !== null}
                                                    className={`w-full text-left px-6 py-4 rounded-xl font-semibold text-lg transition-all ${
                                                        isCorrect
                                                            ? 'bg-green-500 text-white'
                                                            : isWrong
                                                            ? 'bg-red-500 text-white'
                                                            : 'bg-gray-100 hover:bg-gray-200 text-gray-800'
                                                    }`}
                                                >
                                                    {choice}
                                                </button>
                                            );
                                        })}
                                    </div>
                                    
                                    {feedback && (
                                        <div className={`mt-6 p-4 rounded-xl text-center font-bold text-lg ${
                                            feedback === 'correct' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                                        }`}>
                                            {feedback === 'correct' ? '✅ Правильно!' : '❌ Неправильно'}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                );
            }
            
            if (screen === 'leaderboard') {
                return (
                    <div className="min-h-screen bg-gradient-to-br from-purple-500 via-pink-500 to-red-500 flex items-center justify-center p-4">
                        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full">
                            <div className="text-center mb-8">
                                <div className="inline-flex bg-gradient-to-r from-yellow-400 to-orange-500 p-4 rounded-full mb-4">
                                    <Trophy />
                                </div>
                                <h1 className="text-4xl font-bold text-gray-800 mb-2">Игра завершена!</h1>
                                <p className="text-2xl text-gray-600">Ваш счёт: <span className="font-bold text-green-600">{score}</span></p>
                            </div>
                            
                            <div className="mb-8">
                                <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                                    <Users />
                                    Таблица лидеров
                                </h2>
                                {leaderboard.length === 0 ? (
                                    <div className="text-center p-8 bg-gray-50 rounded-xl">
                                        <p className="text-gray-500">Пока нет игроков в рейтинге</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {leaderboard.map((player, idx) => (
                                            <div
                                                key={idx}
                                                className={`flex items-center justify-between p-4 rounded-xl ${
                                                    idx === 0 ? 'bg-yellow-100 border-2 border-yellow-400' :
                                                    idx === 1 ? 'bg-gray-100 border-2 border-gray-400' :
                                                    idx === 2 ? 'bg-orange-100 border-2 border-orange-400' :
                                                    'bg-gray-50'
                                                }`}
                                            >
                                                <div className="flex items-center gap-4">
                                                    <span className="text-2xl font-bold text-gray-600 w-8">#{idx + 1}</span>
                                                    <span className="font-semibold text-lg">{player.name}</span>
                                                </div>
                                                <span className="text-2xl font-bold text-green-600">{player.score}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                            
                            <button
                                onClick={restartGame}
                                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-4 rounded-xl font-bold text-lg hover:shadow-lg transform hover:scale-105 transition-all flex items-center justify-center gap-2"
                            >
                                <Home />
                                Играть ещё раз
                            </button>
                        </div>
                    </div>
                );
            }
        }
        
        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<SprintQuiz />);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return HTML_CONTENT

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
    
    print(f"New WebSocket connection. Total connections: {len(active_connections)}")
    
    try:
        while True:
            data = await ws.receive_json()
            print(f"Received action: {data.get('action')} from {player_id}")
            
            if data["action"] == "register":
                player_id = data["name"]
                players[player_id] = {
                    "score": 0,
                    "start_time": time.time(),
                    "game_active": True
                }
                print(f"Player registered: {player_id}")
                await ws.send_json({
                    "status": "registered",
                    "name": player_id,
                    "total_questions": len(QUESTIONS)
                })
                await broadcast_leaderboard()
            
            elif data["action"] == "start_game":
                if player_id:
                    players[player_id]["start_time"] = time.time()
                    players[player_id]["game_active"] = True
                    players[player_id]["score"] = 0
                    print(f"Game started for: {player_id}")
                    await ws.send_json({"status": "game_started"})
            
            elif data["action"] == "get_question":
                if not QUESTIONS:
                    print("ERROR: No questions available!")
                    await ws.send_json({"error": "No questions available"})
                    continue
                
                q = random.choice(QUESTIONS)
                print(f"Sending question to {player_id}: {q['question'][:50]}...")
                await ws.send_json({
                    "type": "question",
                    "q": q
                })
            
            elif data["action"] == "answer":
                if not player_id or player_id not in players:
                    continue
                
                elapsed = time.time() - players[player_id]["start_time"]
                if elapsed > 60:
                    players[player_id]["game_active"] = False
                    print(f"Game over for {player_id} - time expired")
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
                
                print(f"{player_id} answered {result}. Score: {players[player_id]['score']}")
                
                await ws.send_json({
                    "type": "answer_result",
                    "result": result,
                    "score": players[player_id]["score"],
                    "time_left": max(0, 60 - elapsed)
                })
                
                await broadcast_leaderboard()
            
            elif data["action"] == "get_leaderboard":
                await broadcast_leaderboard()
    
    except WebSocketDisconnect:
        active_connections.discard(ws)
        print(f"WebSocket disconnected. Player: {player_id}. Remaining connections: {len(active_connections)}")
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        active_connections.discard(ws)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting server with {len(QUESTIONS)} questions loaded")
    uvicorn.run(app, host="0.0.0.0", port=8000)