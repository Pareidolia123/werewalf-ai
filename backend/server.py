"""FastAPI 服务器 - 提供游戏API"""
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, Dict, List
import json
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent  # werewolf/
FRONTEND_DIR = BASE_DIR / "frontend"

# 导入游戏模块
import sys
sys.path.append(os.path.dirname(__file__))

from models import Player, GameState, PublicEvent, Role, Phase, Personality
from ai_player import AIPlayer
from llm_provider import QwenLLM, MockLLM, LLMProviderBase
from game_engine import GameEngine

app = FastAPI(title="狼人杀AI对战")

# 存储活跃的WebSocket连接
active_connections: List[WebSocket] = []

# 当前游戏引擎
current_game: Optional[GameEngine] = None


class WebSocketGameEngine(GameEngine):
    """支持WebSocket广播的游戏引擎"""
    
    def __init__(self, llm: LLMProviderBase, ws_callback):
        super().__init__(llm)
        self.ws_callback = ws_callback
    
    async def broadcast(self, event_type: str, data: dict):
        """广播事件到前端"""
        message = {"type": event_type, "data": data}
        await self.ws_callback(message)
    
    async def _run_night(self) -> None:
        """重写夜晚阶段，添加广播"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.NIGHT
        
        await self.broadcast("phase_change", {
            "round": self.game_state.round,
            "phase": "night",
            "message": f"🌙 第 {self.game_state.round} 轮 - 夜晚"
        })
        
        await asyncio.sleep(1)
        
        # 狼人行动
        await self.broadcast("action", {
            "role": "werewolf",
            "message": "🐺 狼人正在选择目标..."
        })
        kill_target = await self._werewolf_action()
        self.game_state.night_kill_target = kill_target
        
        await asyncio.sleep(0.5)
        
        # 预言家行动
        await self.broadcast("action", {
            "role": "seer",
            "message": "🔮 预言家正在查验..."
        })
        await self._seer_action()
        
        await asyncio.sleep(0.5)
        
        # 女巫行动
        await self.broadcast("action", {
            "role": "witch",
            "message": "🧪 女巫正在考虑用药..."
        })
        saved, poisoned = await self._witch_action()
        
        # 结算死亡
        deaths: List[int] = []
        if kill_target and kill_target != saved:
            deaths.append(kill_target)
        if poisoned:
            deaths.append(poisoned)
        
        for pid in deaths:
            player = self.game_state.get_player(pid)
            if player:
                player.is_alive = False
        
        await asyncio.sleep(1)
        
        # 广播天亮消息
        if deaths:
            for pid in deaths:
                player = self.game_state.get_player(pid)
                role_name = self._role_name(player.role) if player else "未知"
                reason = "被狼人击杀" if pid == kill_target else "被女巫毒杀"
                await self.broadcast("death", {
                    "player_id": pid,
                    "role": role_name,
                    "reason": reason,
                    "message": f"💀 {pid}号玩家 {reason}"
                })
                self.game_state.public_history.append(
                    PublicEvent(
                        round=self.game_state.round,
                        phase="night",
                        event_type="death",
                        player_id=pid,
                        content=reason
                    )
                )
        else:
            await self.broadcast("info", {
                "message": "✨ 昨晚是平安夜，没有人死亡"
            })
        
        self.game_state.night_kill_target = None
    
    async def _speech_phase(self) -> None:
        """重写发言阶段"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.DAY_SPEECH
        
        await self.broadcast("phase_change", {
            "round": self.game_state.round,
            "phase": "day_speech",
            "message": f"💬 第 {self.game_state.round} 轮 - 白天发言"
        })
        
        await asyncio.sleep(1)
        
        alive_players = self.game_state.get_alive_players()
        
        for player in alive_players:
            ai = self.ai_players[player.id]
            
            await self.broadcast("speaking", {
                "player_id": player.id,
                "message": f"📢 {player.id}号玩家 正在发言..."
            })
            
            response = await ai.act(self.game_state, "speech")
            speech = response.speech or "（沉默）"
            thought = response.thought or ""
            
            await self.broadcast("speech", {
                "player_id": player.id,
                "speech": speech,
                "thought": thought,
                "message": f"{player.id}号: {speech}"
            })
            
            self.game_state.public_history.append(
                PublicEvent(
                    round=self.game_state.round,
                    phase="day_speech",
                    event_type="speech",
                    player_id=player.id,
                    content=speech
                )
            )
            
            await asyncio.sleep(0.5)
    
    async def _vote_phase(self) -> None:
        """重写投票阶段"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.DAY_VOTE
        
        await self.broadcast("phase_change", {
            "round": self.game_state.round,
            "phase": "day_vote",
            "message": f"🗳️ 第 {self.game_state.round} 轮 - 投票"
        })
        
        await asyncio.sleep(1)
        
        votes: Dict[int, int] = {}
        vote_counts: Dict[int, int] = {}
        
        alive_players = self.game_state.get_alive_players()
        
        for player in alive_players:
            ai = self.ai_players[player.id]
            response = await ai.act(self.game_state, "vote")
            target = self._extract_target(response)
            
            if target and target != player.id:
                votes[player.id] = target
                vote_counts[target] = vote_counts.get(target, 0) + 1
                
                await self.broadcast("vote", {
                    "player_id": player.id,
                    "target": target,
                    "message": f"{player.id}号 → 投票给 {target}号"
                })
                
                self.game_state.public_history.append(
                    PublicEvent(
                        round=self.game_state.round,
                        phase="day_vote",
                        event_type="vote",
                        player_id=player.id,
                        content=f"投票给{target}号",
                        extra={"target": target}
                    )
                )
            
            await asyncio.sleep(0.3)
        
        # 统计结果
        await asyncio.sleep(1)
        
        if vote_counts:
            max_votes = max(vote_counts.values())
            candidates = [pid for pid, count in vote_counts.items() if count == max_votes]
            
            await self.broadcast("vote_result", {
                "counts": vote_counts,
                "message": "📊 投票统计完成"
            })
            
            if len(candidates) == 1:
                eliminated = candidates[0]
                player = self.game_state.get_player(eliminated)
                if player:
                    player.is_alive = False
                    role_name = self._role_name(player.role)
                    
                    await self.broadcast("eliminated", {
                        "player_id": eliminated,
                        "role": role_name,
                        "votes": max_votes,
                        "message": f"⚰️ {eliminated}号玩家 被放逐（{role_name}）"
                    })
                    
                    self.game_state.public_history.append(
                        PublicEvent(
                            round=self.game_state.round,
                            phase="day_vote",
                            event_type="death",
                            player_id=eliminated,
                            content="被投票放逐"
                        )
                    )
            else:
                await self.broadcast("info", {
                    "message": "⚖️ 平票！无人被放逐"
                })
    
    async def run_game(self) -> None:
        """运行游戏"""
        if not self.game_state:
            self.setup_game()
        
        assert self.game_state is not None
        
        # 广播游戏开始和角色信息
        players_info = []
        for p in self.game_state.players:
            players_info.append({
                "id": p.id,
                "role": self._role_name(p.role),
                "role_key": p.role.value,
                "personality": p.personality.value,
                "is_alive": p.is_alive
            })
        
        await self.broadcast("game_start", {
            "players": players_info,
            "message": "🎮 游戏开始！天黑请闭眼..."
        })
        
        await asyncio.sleep(2)
        
        while not self._check_game_over():
            await self._run_night()
            
            if self._check_game_over():
                break
            
            await self._run_day()
            
            self.game_state.round += 1
            await asyncio.sleep(1)
        
        # 游戏结束
        alive = self.game_state.get_alive_players()
        wolves_alive = sum(1 for p in alive if p.role == Role.WEREWOLF)
        
        winner = "werewolf" if wolves_alive > 0 else "villager"
        
        final_players = []
        for p in self.game_state.players:
            final_players.append({
                "id": p.id,
                "role": self._role_name(p.role),
                "role_key": p.role.value,
                "is_alive": p.is_alive
            })
        
        await self.broadcast("game_over", {
            "winner": winner,
            "players": final_players,
            "message": "🐺 狼人胜利！" if winner == "werewolf" else "🎉 好人胜利！"
        })


async def broadcast_to_all(message: dict):
    """广播消息到所有连接"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接处理"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "start_game":
                # 获取API Key
                # api_key = data.get("api_key") or os.getenv("QWEN_API_KEY")
                api_key = 'sk-2f171ed5cf8340c0a9886027eb32147a'
                
                if api_key:
                    llm = QwenLLM(api_key=api_key)
                    await websocket.send_json({
                        "type": "info",
                        "data": {"message": "✅ 使用通义千问 API"}
                    })
                else:
                    llm = MockLLM()
                    await websocket.send_json({
                        "type": "info",
                        "data": {"message": "⚠️ 未设置API Key，使用模拟模式"}
                    })
                
                # 创建游戏引擎
                engine = WebSocketGameEngine(llm, broadcast_to_all)
                
                # 运行游戏
                await engine.run_game()
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)


@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse(FRONTEND_DIR / "index.html")


# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    print(f"📁 前端目录: {FRONTEND_DIR}")
    print(f"🌐 启动服务器: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)