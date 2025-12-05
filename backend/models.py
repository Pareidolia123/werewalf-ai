"""数据模型定义"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from enum import Enum


class Role(str, Enum):
    WEREWOLF = "werewolf"
    SEER = "seer"
    WITCH = "witch"
    VILLAGER = "villager"


class Phase(str, Enum):
    NIGHT = "night"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"


class Personality(str, Enum):
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    CUNNING = "cunning"


@dataclass
class Player:
    """玩家数据"""
    id: int
    role: Role
    is_alive: bool = True
    is_human: bool = False
    personality: Personality = Personality.CUNNING
    thinking_history: List[str] = field(default_factory=list)
    
    # 角色特有信息
    teammates: List[int] = field(default_factory=list)  # 狼人队友
    investigated: Dict[int, bool] = field(default_factory=dict)  # 预言家查验结果 {玩家id: 是否好人}
    has_antidote: bool = True  # 女巫解药
    has_poison: bool = True    # 女巫毒药


@dataclass
class PublicEvent:
    """公开事件记录"""
    round: int
    phase: str
    event_type: str  # "speech" | "vote" | "death" | "vote_result"
    player_id: Optional[int]
    content: str
    extra: Dict = field(default_factory=dict)


@dataclass
class GameState:
    """游戏状态"""
    round: int = 1
    phase: Phase = Phase.NIGHT
    players: List[Player] = field(default_factory=list)
    public_history: List[PublicEvent] = field(default_factory=list)
    
    # 当前夜晚信息（仅相关角色可见）
    night_kill_target: Optional[int] = None  # 狼人今晚的击杀目标
    
    def get_alive_players(self) -> List[Player]:
        return [p for p in self.players if p.is_alive]
    
    def get_alive_player_ids(self) -> List[int]:
        return [p.id for p in self.players if p.is_alive]
    
    def get_player(self, player_id: int) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None


@dataclass
class AIResponse:
    """AI响应结构"""
    thought: str           # 内心独白（不公开）
    speech: Optional[str] = None  # 公开发言
    action: Optional[Dict] = None # 具体行动
    raw_response: str = ""  # 原始响应，用于调试
