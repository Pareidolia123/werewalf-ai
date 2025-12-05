"""Prompt构建器 - 形式化的prompt组装"""
from typing import Optional, Dict
from models import Player, GameState, Role, Phase, Personality, PublicEvent


class PromptBuilder:
    """
    形式化的Prompt构建器
    将prompt拆分为多个独立section，方便调试和修改
    """
    
    def build_prompt(
        self, 
        player: Player, 
        game_state: GameState, 
        action_type: str  # "night_action" | "speech" | "vote"
    ) -> str:
        """构建完整的prompt"""
        sections = [
            self._build_rules_section(),
            self._build_role_section(player, game_state),
            self._build_personality_section(player),
            self._build_context_section(game_state, player),
            self._build_thinking_history_section(player),
            self._build_action_instruction(action_type, player, game_state),
            self._build_output_format(action_type),
        ]
        
        # 过滤掉空字符串
        non_empty_sections = [s for s in sections if s and s.strip()]
        return "\n\n".join(non_empty_sections)
    
    def build_system_prompt(self) -> str:
        """构建system message"""
        return """你是一个狼人杀游戏的AI玩家。你需要：
1. 根据你的角色身份和游戏目标做出决策
2. 在发言时隐藏或透露适当的信息
3. 通过逻辑推理分析其他玩家的身份
4. 严格按照要求的JSON格式输出

重要：你的"内心独白"(thought)是你的私密思考，不会被其他玩家看到。
你的"发言"(speech)是公开的，所有玩家都能听到。"""

    def _phase_to_chinese(self, phase: Phase) -> str:
        """阶段转中文"""
        mapping: Dict[Phase, str] = {
        Phase.NIGHT: "夜晚",
        Phase.DAY_SPEECH: "白天发言",
        Phase.DAY_VOTE: "白天投票"
        }
        return mapping.get(phase, str(phase.value))

    def _format_event(self, event: PublicEvent) -> str:
        """格式化事件为可读文本"""
        if event.event_type == "speech":
            return f"{event.player_id}号发言：「{event.content}」"
        elif event.event_type == "vote":
            target = event.extra.get("target", "?")
            return f"{event.player_id}号 投票给 {target}号"
        elif event.event_type == "death":
            return f"💀 {event.player_id}号 死亡（{event.content}）"
        elif event.event_type == "vote_result":
            return f"投票结果：{event.content}"
        return event.content

    # ========== 各个Section的构建方法 ==========
    
    def _build_rules_section(self) -> str:
        """游戏规则section"""
        return """# 狼人杀游戏规则

        ## 游戏目标
        - 好人阵营（村民、预言家、女巫）：找出并淘汰所有狼人
        - 狼人阵营：使狼人数量 ≥ 好人数量

        ## 角色说明
        - 🐺 狼人：每晚可以击杀一名玩家，知道队友身份
        - 🔮 预言家：每晚可以查验一名玩家是好人还是狼人
        - 🧪 女巫：有一瓶解药（救人）和一瓶毒药（杀人），各只能用一次
        - 👤 村民：无特殊能力，通过发言和投票找出狼人

        ## 游戏流程
        1. 夜晚：狼人击杀 → 预言家查验 → 女巫用药
        2. 白天：公布死讯 → 依次发言 → 投票放逐"""
    
    def _build_role_section(self, player: Player, game_state: GameState) -> str:
        """角色身份section"""
        role_names: Dict[Role, str] = {
            Role.WEREWOLF: "狼人",
            Role.SEER: "预言家", 
            Role.WITCH: "女巫",
            Role.VILLAGER: "村民"
        }
        
        role_name = role_names.get(player.role, "未知角色")
        camp = "狼人阵营" if player.role == Role.WEREWOLF else "好人阵营"
        
        section = f"""## 你的身份
- 你是 **{player.id}号玩家**
- 你的角色是 **{role_name}**
- 你的阵营是 **{camp}**"""
        
        # 狼人知道队友
        if player.role == Role.WEREWOLF and player.teammates:
            teammates_str = ", ".join([f"{t}号" for t in player.teammates])
            section += f"\n- 你的狼人队友是：{teammates_str}"
        
        # 预言家的查验记录
        if player.role == Role.SEER and player.investigated:
            section += "\n- 你的查验记录："
            for pid, is_good in player.investigated.items():
                result = "好人" if is_good else "狼人"
                section += f"\n  - {pid}号玩家是【{result}】"
        
        # 女巫的药水状态
        if player.role == Role.WITCH:
            antidote_status = "可用" if player.has_antidote else "已使用"
            poison_status = "可用" if player.has_poison else "已使用"
            section += f"\n- 解药状态：{antidote_status}"
            section += f"\n- 毒药状态：{poison_status}"
        
        return section
    
    def _build_personality_section(self, player: Player) -> str:
        """性格特点section"""
        personalities: Dict[Personality, str] = {
            Personality.AGGRESSIVE: """## 你的性格特点
性格：激进、好斗、喜欢主导局面
行为特点：主动发起攻击，敢于冒险，善于制造混乱
发言风格：直接、强势、不怕得罪人
注意：所有发言和决策都应符合你的性格特点""",

            Personality.CONSERVATIVE: """## 你的性格特点
性格：保守、谨慎、避免风险
行为特点：观察仔细，不轻易表态，喜欢隐藏自己
发言风格：谨慎、含蓄、留有余地
注意：所有发言和决策都应符合你的性格特点""",

            Personality.CUNNING: """## 你的性格特点
性格：狡猾、善于伪装、精于算计
行为特点：隐藏真实意图，误导他人，长期布局
发言风格：模棱两可、善于试探、不暴露关键信息
注意：所有发言和决策都应符合你的性格特点"""
        }
        
        return personalities.get(player.personality, "")
    
    def _build_context_section(self, game_state: GameState, player: Player) -> str:
        """当前局面上下文section"""
        alive_ids = game_state.get_alive_player_ids()
        dead_ids = [p.id for p in game_state.players if not p.is_alive]
        
        phase_name = self._phase_to_chinese(game_state.phase)
        alive_str = ", ".join([f"{i}号" for i in alive_ids])
        
        section = f"""## 当前游戏局面
- 当前是第 **{game_state.round}** 轮
- 当前阶段：**{phase_name}**
- 存活玩家：{alive_str}（共{len(alive_ids)}人）"""
        
        if dead_ids:
            dead_str = ", ".join([f"{i}号" for i in dead_ids])
            section += f"\n- 已死亡玩家：{dead_str}"
        
        # 女巫在夜晚需要知道被杀的人
        if player.role == Role.WITCH and game_state.phase == Phase.NIGHT:
            if game_state.night_kill_target:
                section += f"\n- 【女巫信息】今晚狼人击杀了 **{game_state.night_kill_target}号** 玩家"
            else:
                section += "\n- 【女巫信息】今晚没有人被狼人击杀"
        
        # 添加历史事件
        if game_state.public_history:
            section += "\n\n### 历史事件记录"
            # 只显示最近10条
            recent_events = game_state.public_history[-10:]
            for event in recent_events:
                formatted_event = self._format_event(event)
                section += f"\n- [{event.phase}] {formatted_event}"
        
        return section
    
    def _build_thinking_history_section(self, player: Player) -> str:
        """内心独白历史section"""
        if not player.thinking_history:
            return ""
        
        section = "## 你之前的内心独白（只有你自己知道）"
        # 只保留最近3次
        recent = player.thinking_history[-3:]
        total_count = len(player.thinking_history)
        recent_count = len(recent)
        
        for i, thought in enumerate(recent):
            thought_index = total_count - recent_count + i + 1
            section += f"\n第{thought_index}次思考：{thought}"
        
        return section
    
    def _build_action_instruction(
        self, 
        action_type: str, 
        player: Player,
        game_state: GameState
    ) -> str:
        """行动指令section"""
        alive_ids = game_state.get_alive_player_ids()
        other_alive = [i for i in alive_ids if i != player.id]
        
        if action_type == "speech":
            return """## 现在轮到你发言
请发表你的看法，可以：
- 分析局势和其他玩家的嫌疑
- 为自己辩护或指控他人
- 隐藏或透露信息（根据你的角色策略）

发言长度：30-80字的自然对话"""
        
        elif action_type == "vote":
            targets = ", ".join([f"{i}号" for i in other_alive])
            return f"""## 现在是投票环节
请选择一名玩家进行投票放逐。
可投票对象：{targets}

请谨慎选择，你的一票可能决定游戏走向。"""
        
        elif action_type == "night_action":
            return self._build_night_action_instruction(player, game_state)
        
        # 默认返回空字符串
        return ""
    
    def _build_night_action_instruction(self, player: Player, game_state: GameState) -> str:
        """夜晚行动指令"""
        alive_ids = game_state.get_alive_player_ids()
        other_alive = [i for i in alive_ids if i != player.id]
        targets = ", ".join([f"{i}号" for i in other_alive])
        
        if player.role == Role.WEREWOLF:
            return f"""## 夜晚行动 - 狼人击杀
你和你的狼人队友需要选择一名玩家击杀。
可击杀对象：{targets}

请选择对狼人阵营最有利的目标。"""
        
        elif player.role == Role.SEER:
            # 排除已经查验过的
            can_investigate = [i for i in other_alive if i not in player.investigated]
            investigate_targets = ", ".join([f"{i}号" for i in can_investigate])
            return f"""## 夜晚行动 - 预言家查验
你可以选择一名玩家查验其身份。
可查验对象：{investigate_targets}

请选择你最想确认身份的玩家。"""
        
        elif player.role == Role.WITCH:
            instruction = "## 夜晚行动 - 女巫用药\n"
            
            if player.has_antidote and game_state.night_kill_target:
                instruction += f"- 你可以使用【解药】救活 {game_state.night_kill_target}号 玩家\n"
            elif not player.has_antidote:
                instruction += "- 你的解药已经用过了\n"
            else:
                instruction += "- 今晚没有人被杀，无需使用解药\n"
            
            if player.has_poison:
                poison_targets = ", ".join([f"{i}号" for i in other_alive])
                instruction += f"- 你可以使用【毒药】毒杀一名玩家：{poison_targets}\n"
            else:
                instruction += "- 你的毒药已经用过了\n"
            
            instruction += "\n你可以选择：使用解药、使用毒药、两者都用、或者什么都不做"
            return instruction
        
        # 村民没有夜晚行动
        return "## 夜晚\n你没有特殊能力，请等待天亮。"
    
    def _build_output_format(self, action_type: str) -> str:
        """输出格式要求section"""
        base_format = """## 输出格式要求
请严格按照以下JSON格式输出，不要添加任何其他文字：

```json
{
    "thought": "你的内心独白，详细的思考过程（其他玩家看不到）","""
        
        if action_type == "speech":
            return base_format + """
    "speech": "你的公开发言，30-80字"
}
```"""
        
        elif action_type == "vote":
            return base_format + """
    "speech": "投票时的简短发言（可选）",
    "action": {
        "type": "vote",
        "target": 玩家编号（数字）,
        "reason": "投票理由"
    }
}
```"""
        
        elif action_type == "night_action":
            return base_format + """
    "action": {
        "type": "行动类型",
        "target": 目标玩家编号（数字）,
        "reason": "选择理由"
    }
}
行动类型说明：

狼人：{"type": "kill", "target": 编号, "reason": "理由"}

预言家：{"type": "investigate", "target": 编号, "reason": "理由"}

女巫：{"type": "save", "target": 编号} 或 {"type": "poison", "target": 编号} 或 {"type": "idle"}"""

  # 默认格式
        return base_format + "\n}\n```"


