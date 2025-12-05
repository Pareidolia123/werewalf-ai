"""AI玩家封装"""
import json
import re
from typing import Optional
from models import Player, GameState, AIResponse
from prompt_builder import PromptBuilder
from llm_provider import LLMProviderBase


class AIPlayer:
    """AI玩家"""
    
    def __init__(self, player: Player, llm: LLMProviderBase):
        self.player = player
        self.llm = llm
        self.prompt_builder = PromptBuilder()
    
    async def act(self, game_state: GameState, action_type: str) -> AIResponse:
        """
        执行一次行动
        
        Args:
            game_state: 当前游戏状态
            action_type: "night_action" | "speech" | "vote"
        
        Returns:
            AIResponse: 包含思考、发言和行动
        """
        # 1. 构建prompt
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_prompt(
            self.player, game_state, action_type
        )
        
        # 2. 调用LLM（直接传两个字符串参数）
        print(f"\n{'='*60}")
        print(f"🤖 AI玩家 {self.player.id}号 ({self.player.role.value}) 正在思考...")
        print(f"{'='*60}")
        print(f"[Prompt]\n{user_prompt[:500]}...")  # 只打印前500字符
        
        raw_response = await self.llm.call(system_prompt, user_prompt)
        
        print(f"\n[Raw Response]\n{raw_response}")
        
        # 3. 解析响应
        response = self._parse_response(raw_response)
        
        # 4. 保存内心独白到历史
        if response.thought:
            self.player.thinking_history.append(response.thought)
        
        return response
    
    def _parse_response(self, raw: str) -> AIResponse:
        """解析LLM的JSON响应"""
        try:
            # 尝试提取JSON
            json_str = self._extract_json(raw)
            data = json.loads(json_str)
            
            return AIResponse(
                thought=data.get("thought", ""),
                speech=data.get("speech"),
                action=data.get("action"),
                raw_response=raw
            )
        except Exception as e:
            print(f"⚠️ JSON解析失败: {e}")
            # 返回一个fallback响应
            return AIResponse(
                thought=f"[解析失败] {raw[:200]}",
                speech="我需要再想想...",
                action=None,
                raw_response=raw
            )
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        # 尝试匹配 ```json ... ``` 格式
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1)
        
        # 尝试匹配 ``` ... ``` 格式
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1)
        
        # 尝试直接找 { ... }
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        
        # 返回原文本，让json.loads报错
        return text
