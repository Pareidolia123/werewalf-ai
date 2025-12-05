"""游戏引擎 - 控制游戏流程"""
import random
from typing import Optional, Dict, List
from models import Player, GameState, PublicEvent, Role, Phase, Personality, AIResponse
from ai_player import AIPlayer
from llm_provider import LLMProviderBase, QwenLLM


class GameEngine:
    """狼人杀游戏引擎"""
    
    def __init__(self, llm: LLMProviderBase, player_count: int = 6):
        self.llm = llm
        self.player_count = player_count
        self.game_state: Optional[GameState] = None
        self.ai_players: Dict[int, AIPlayer] = {}
        
    def setup_game(self) -> None:
        """初始化游戏"""
        print("\n🎮 正在初始化游戏...")
        
        # 分配角色：2狼人 + 1预言家 + 1女巫 + 2村民
        roles = [
            Role.WEREWOLF, Role.WEREWOLF,
            Role.SEER, Role.WITCH,
            Role.VILLAGER, Role.VILLAGER
        ]
        random.shuffle(roles)
        
        # 分配性格
        personalities = list(Personality)
        
        # 创建玩家
        players: List[Player] = []
        for i, role in enumerate(roles):
            player = Player(
                id=i + 1,
                role=role,
                personality=random.choice(personalities)
            )
            players.append(player)
        
        # 设置狼人队友关系
        werewolves = [p for p in players if p.role == Role.WEREWOLF]
        for wolf in werewolves:
            wolf.teammates = [w.id for w in werewolves if w.id != wolf.id]
        
        # 创建游戏状态
        self.game_state = GameState(
            round=1,
            phase=Phase.NIGHT,
            players=players,
            public_history=[]
        )
        
        # 为每个玩家创建AI
        for player in players:
            self.ai_players[player.id] = AIPlayer(player, self.llm)
        
        # 打印角色分配（调试用）
        print("\n📋 角色分配（调试信息）：")
        for p in players:
            print(f"  {p.id}号: {self._role_name(p.role)} ({p.personality.value})")
        print()
    
    async def run_game(self) -> None:
        """运行完整游戏"""
        if not self.game_state:
            self.setup_game()
        
        assert self.game_state is not None
        
        print("\n" + "="*80)
        print("🌙 游戏开始！天黑请闭眼...")
        print("="*80)
        
        while not self._check_game_over():
            await self._run_night()
            
            if self._check_game_over():
                break
                
            await self._run_day()
            
            self.game_state.round += 1
        
        self._announce_winner()
    
    # ==================== 夜晚阶段 ====================
    
    async def _run_night(self) -> None:
        """执行夜晚阶段"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.NIGHT
        
        print(f"\n{'='*80}")
        print(f"🌙 第 {self.game_state.round} 轮 - 夜晚")
        print(f"{'='*80}")
        
        # 1. 狼人行动
        kill_target = await self._werewolf_action()
        self.game_state.night_kill_target = kill_target
        
        # 2. 预言家行动
        await self._seer_action()
        
        # 3. 女巫行动
        saved, poisoned = await self._witch_action()
        
        # 4. 结算夜晚死亡
        deaths: List[int] = []
        
        if kill_target and kill_target != saved:
            deaths.append(kill_target)
        
        if poisoned:
            deaths.append(poisoned)
        
        # 处理死亡
        for pid in deaths:
            player = self.game_state.get_player(pid)
            if player:
                player.is_alive = False
        
        # 记录死亡事件
        print(f"\n☀️ 天亮了...")
        if deaths:
            for pid in deaths:
                reason = "被狼人击杀" if pid == kill_target else "被女巫毒杀"
                print(f"  💀 {pid}号玩家 死亡（{reason}）")
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
            print("  ✨ 昨晚是平安夜，没有人死亡")
        
        # 清除夜晚临时状态
        self.game_state.night_kill_target = None
    
    async def _werewolf_action(self) -> Optional[int]:
        """狼人击杀"""
        assert self.game_state is not None
        
        wolves = [p for p in self.game_state.players 
                  if p.role == Role.WEREWOLF and p.is_alive]
        
        if not wolves:
            return None
        
        # 让第一个狼人决定目标（简化处理）
        wolf = wolves[0]
        ai = self.ai_players[wolf.id]
        
        print(f"\n🐺 狼人 {wolf.id}号 正在选择击杀目标...")
        response = await ai.act(self.game_state, "night_action")
        
        target = self._extract_target(response)
        if target:
            print(f"  → 狼人决定击杀 {target}号")
        
        return target
    
    async def _seer_action(self) -> None:
        """预言家查验"""
        assert self.game_state is not None
        
        seer = next((p for p in self.game_state.players 
                     if p.role == Role.SEER and p.is_alive), None)
        
        if not seer:
            return
        
        ai = self.ai_players[seer.id]
        
        print(f"\n🔮 预言家 {seer.id}号 正在选择查验目标...")
        response = await ai.act(self.game_state, "night_action")
        
        target = self._extract_target(response)
        if target:
            target_player = self.game_state.get_player(target)
            if target_player:
                is_good = target_player.role != Role.WEREWOLF
                seer.investigated[target] = is_good
                result = "好人" if is_good else "狼人"
                print(f"  → 查验结果：{target}号 是 【{result}】")
    
    async def _witch_action(self) -> tuple[Optional[int], Optional[int]]:
        """女巫用药，返回 (救的人, 毒的人)"""
        assert self.game_state is not None
        
        witch = next((p for p in self.game_state.players 
                      if p.role == Role.WITCH and p.is_alive), None)
        
        if not witch:
            return None, None
        
        ai = self.ai_players[witch.id]
        
        print(f"\n🧪 女巫 {witch.id}号 正在考虑用药...")
        response = await ai.act(self.game_state, "night_action")
        
        saved = None
        poisoned = None
        
        if response.action:
            action_type = response.action.get("type")
            target = response.action.get("target")
            
            if action_type == "save" and witch.has_antidote:
                saved = target
                witch.has_antidote = False
                print(f"  → 女巫使用解药救了 {target}号")
            
            elif action_type == "poison" and witch.has_poison:
                poisoned = target
                witch.has_poison = False
                print(f"  → 女巫使用毒药毒杀 {target}号")
            
            elif action_type == "idle":
                print(f"  → 女巫选择不用药")
        
        return saved, poisoned
    
    # ==================== 白天阶段 ====================
    
    async def _run_day(self) -> None:
        """执行白天阶段"""
        assert self.game_state is not None
        
        # 发言阶段
        await self._speech_phase()
        
        if self._check_game_over():
            return
        
        # 投票阶段
        await self._vote_phase()
    
    async def _speech_phase(self) -> None:
        """发言阶段"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.DAY_SPEECH
        
        print(f"\n{'='*80}")
        print(f"💬 第 {self.game_state.round} 轮 - 白天发言")
        print(f"{'='*80}")
        
        alive_players = self.game_state.get_alive_players()
        
        for player in alive_players:
            ai = self.ai_players[player.id]
            
            print(f"\n📢 {player.id}号玩家 发言：")
            response = await ai.act(self.game_state, "speech")
            
            speech = response.speech or "（沉默）"
            print(f"   「{speech}」")
            
            # 记录发言
            self.game_state.public_history.append(
                PublicEvent(
                    round=self.game_state.round,
                    phase="day_speech",
                    event_type="speech",
                    player_id=player.id,
                    content=speech
                )
            )
    
    async def _vote_phase(self) -> None:
        """投票阶段"""
        assert self.game_state is not None
        
        self.game_state.phase = Phase.DAY_VOTE
        
        print(f"\n{'='*80}")
        print(f"🗳️ 第 {self.game_state.round} 轮 - 投票")
        print(f"{'='*80}")
        
        votes: Dict[int, int] = {}  # voter_id -> target_id
        vote_counts: Dict[int, int] = {}  # target_id -> count
        
        alive_players = self.game_state.get_alive_players()
        
        for player in alive_players:
            ai = self.ai_players[player.id]
            
            response = await ai.act(self.game_state, "vote")
            target = self._extract_target(response)
            
            if target and target != player.id:
                votes[player.id] = target
                vote_counts[target] = vote_counts.get(target, 0) + 1
                print(f"  {player.id}号 → 投票给 {target}号")
                
                # 记录投票
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
        
        # 统计结果
        if vote_counts:
            max_votes = max(vote_counts.values())
            candidates = [pid for pid, count in vote_counts.items() if count == max_votes]
            
            print(f"\n📊 投票结果：")
            for pid, count in sorted(vote_counts.items(), key=lambda x: -x[1]):
                print(f"  {pid}号: {count}票")
            
            if len(candidates) == 1:
                eliminated = candidates[0]
                player = self.game_state.get_player(eliminated)
                if player:
                    player.is_alive = False
                    print(f"\n⚰️ {eliminated}号玩家 被投票放逐（{self._role_name(player.role)}）")
                    
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
                print(f"\n⚖️ 平票！无人被放逐")
        else:
            print("\n🤷 没有有效投票")
    
    # ==================== 工具方法 ====================
    
    def _extract_target(self, response: AIResponse) -> Optional[int]:
        """从AI响应中提取目标"""
        if response.action and isinstance(response.action.get("target"), int):
            return response.action["target"]
        return None
    
    def _check_game_over(self) -> bool:
        """检查游戏是否结束"""
        assert self.game_state is not None
        
        alive = self.game_state.get_alive_players()
        wolves_alive = sum(1 for p in alive if p.role == Role.WEREWOLF)
        villagers_alive = sum(1 for p in alive if p.role != Role.WEREWOLF)
        
        # 狼人全死 -> 好人胜
        if wolves_alive == 0:
            return True
        
        # 狼人 >= 好人 -> 狼人胜
        if wolves_alive >= villagers_alive:
            return True
        
        return False
    
    def _announce_winner(self) -> None:
        """宣布胜者"""
        assert self.game_state is not None
        
        alive = self.game_state.get_alive_players()
        wolves_alive = sum(1 for p in alive if p.role == Role.WEREWOLF)
        
        print("\n" + "="*80)
        print("🏆 游戏结束！")
        print("="*80)
        
        if wolves_alive == 0:
            print("🎉 好人阵营胜利！所有狼人已被消灭！")
        else:
            print("🐺 狼人阵营胜利！狼人已经控制了村庄！")
        
        print("\n📋 最终角色揭晓：")
        for p in self.game_state.players:
            status = "存活" if p.is_alive else "死亡"
            print(f"  {p.id}号: {self._role_name(p.role)} [{status}]")
    
    def _role_name(self, role: Role) -> str:
        """角色转中文名"""
        names = {
            Role.WEREWOLF: "🐺狼人",
            Role.SEER: "🔮预言家",
            Role.WITCH: "🧪女巫",
            Role.VILLAGER: "👤村民"
        }
        return names.get(role, str(role))
