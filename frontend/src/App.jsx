import React, { useState, useEffect, useRef } from 'react';
import { Trophy, Clock, Users, Play, Home } from 'lucide-react';

export default function SprintQuiz() {
  const [ws, setWs] = useState(null);
  const [screen, setScreen] = useState('home'); // home, game, leaderboard
  const [playerName, setPlayerName] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [score, setScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(60);
  const [leaderboard, setLeaderboard] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [isRegistered, setIsRegistered] = useState(false);
  const timerRef = useRef(null);

  // WebSocket URL - замени на свой Render backend URL после деплоя
  const WS_URL = 'ws://localhost:8000/ws';
  // const WS_URL = 'wss://your-backend.onrender.com/ws';

  useEffect(() => {
    return () => {
      if (ws) ws.close();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [ws]);

  const connectWebSocket = () => {
    const socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
      console.log('WebSocket подключен');
      setWs(socket);
    };
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.status === 'registered') {
        setIsRegistered(true);
      }
      
      if (data.type === 'question') {
        setCurrentQuestion(data.q);
        setFeedback(null);
      }
      
      if (data.type === 'answer_result') {
        setScore(data.score);
        setFeedback(data.result);
        
        setTimeout(() => {
          setFeedback(null);
          socket.send(JSON.stringify({ action: 'get_question' }));
        }, 800);
      }
      
      if (data.type === 'leaderboard') {
        setLeaderboard(data.players);
      }
      
      if (data.type === 'game_over') {
        endGame(data.final_score);
      }
    };
    
    socket.onerror = (error) => {
      console.error('WebSocket ошибка:', error);
    };
    
    socket.onclose = () => {
      console.log('WebSocket отключен');
    };
  };

  const startGame = () => {
    if (!playerName.trim()) {
      alert('Введите ваше имя!');
      return;
    }
    
    connectWebSocket();
  };

  const registerAndStart = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        action: 'register',
        name: playerName
      }));
      
      setTimeout(() => {
        ws.send(JSON.stringify({ action: 'start_game' }));
        ws.send(JSON.stringify({ action: 'get_question' }));
        setScreen('game');
        setScore(0);
        setTimeLeft(60);
        startTimer();
      }, 500);
    }
  };

  const startTimer = () => {
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
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    setScore(finalScore);
    setScreen('leaderboard');
    if (ws) {
      ws.send(JSON.stringify({ action: 'get_leaderboard' }));
    }
  };

  const handleAnswer = (choice) => {
    if (!currentQuestion || feedback) return;
    
    const answer = choice.charAt(0);
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
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
    if (ws) ws.close();
  };

  // HOME SCREEN
  if (screen === 'home') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full">
          <div className="text-center mb-8">
            <div className="inline-block bg-gradient-to-r from-yellow-400 to-orange-500 p-4 rounded-full mb-4">
              <Trophy className="w-12 h-12 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Sprint Quiz</h1>
            <p className="text-gray-600">60 секунд. Максимум правильных ответов.</p>
          </div>
          
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Введите ваше имя"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && startGame()}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:border-blue-500 focus:outline-none text-lg"
            />
            
            <button
              onClick={startGame}
              disabled={!playerName.trim()}
              className="w-full bg-gradient-to-r from-green-400 to-blue-500 text-white py-4 rounded-xl font-bold text-lg hover:shadow-lg transform hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <Play className="w-6 h-6" />
              Начать игру
            </button>
          </div>
          
          {ws && !isRegistered && (
            <div className="mt-4 text-center">
              <button
                onClick={registerAndStart}
                className="text-blue-600 font-semibold hover:underline"
              >
                Подключиться к игре
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // GAME SCREEN
  if (screen === 'game') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-4">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="bg-white rounded-2xl shadow-lg p-4 mb-4 flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div className="bg-blue-100 p-3 rounded-xl">
                <Users className="w-6 h-6 text-blue-600" />
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
                <Clock className="w-6 h-6 text-red-600" />
                <span className="text-2xl font-bold text-red-600">{timeLeft}s</span>
              </div>
            </div>
          </div>
          
          {/* Question Card */}
          {currentQuestion && (
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
                      className={`w-full text-left px-6 py-4 rounded-xl font-semibold text-lg transition-all transform hover:scale-102 ${
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

  // LEADERBOARD SCREEN
  if (screen === 'leaderboard') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-500 via-pink-500 to-red-500 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full">
          <div className="text-center mb-8">
            <div className="inline-block bg-gradient-to-r from-yellow-400 to-orange-500 p-4 rounded-full mb-4">
              <Trophy className="w-16 h-16 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Игра завершена!</h1>
            <p className="text-2xl text-gray-600">Ваш счёт: <span className="font-bold text-green-600">{score}</span></p>
          </div>
          
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Users className="w-6 h-6" />
              Таблица лидеров
            </h2>
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
          </div>
          
          <button
            onClick={restartGame}
            className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-4 rounded-xl font-bold text-lg hover:shadow-lg transform hover:scale-105 transition-all flex items-center justify-center gap-2"
          >
            <Home className="w-6 h-6" />
            Играть ещё раз
          </button>
        </div>
      </div>
    );
  }
}