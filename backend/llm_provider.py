"""LLM 提供者封装"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
import json
import re


class LLMProviderBase(ABC):
    """LLM 基类"""
    
    @abstractmethod
    async def call(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM，返回响应文本"""
        pass


class QwenLLM(LLMProviderBase):
    """通义千问 LLM"""
    
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
    
    async def call(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用通义千问 API
        
        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
        
        Returns:
            模型响应的文本内容
        """
        try:
            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=1000
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"❌ API 调用错误: {e}")
            return '{"thought": "API调用失败", "speech": "...", "action": null}'


class MockLLM(LLMProviderBase):
    """模拟 LLM（用于测试）"""
    
    async def call(self, system_prompt: str, user_prompt: str) -> str:
        """返回模拟响应"""
        import random
        
        # 检测是什么类型的请求
        if "夜晚行动" in user_prompt or "night" in user_prompt.lower() or "击杀" in user_prompt:
            # 夜晚行动
            if "狼人" in system_prompt:
                target = random.randint(1, 6)
                return json.dumps({
                    "thought": f"我要击杀{target}号，他看起来像预言家",
                    "action": {"type": "kill", "target": target}
                }, ensure_ascii=False)
            
            elif "预言家" in system_prompt:
                target = random.randint(1, 6)
                return json.dumps({
                    "thought": f"今晚查验{target}号",
                    "action": {"type": "investigate", "target": target}
                }, ensure_ascii=False)
            
            elif "女巫" in system_prompt:
                actions = [
                    {"thought": "先观望一下", "action": {"type": "idle"}},
                    {"thought": "救人要紧", "action": {"type": "save", "target": random.randint(1, 6)}},
                ]
                return json.dumps(random.choice(actions), ensure_ascii=False)
            else:
                # 村民
                return json.dumps({
                    "thought": "我是村民，夜晚没有行动",
                    "action": {"type": "idle"}
                }, ensure_ascii=False)
        
        elif "发言" in user_prompt or "speech" in user_prompt.lower():
            # 发言阶段
            speeches = [
                {"thought": "保持低调", "speech": "我是普通村民，昨晚没有收到任何信息。我觉得大家应该多发言，找出狼人。"},
                {"thought": "引导投票", "speech": "我注意到有些人发言闪躲，我建议大家关注一下那些不太说话的人。"},
                {"thought": "假装好人", "speech": "我昨晚被狼人攻击了但是被救了，我怀疑狼人在我们中间潜伏。"},
                {"thought": "跟风发言", "speech": "同意楼上的分析，我也觉得我们应该投票给可疑的人。"},
                {"thought": "表明立场", "speech": "我觉得我们要理性分析，不能盲目跟票，大家说说自己的看法吧。"},
            ]
            return json.dumps(random.choice(speeches), ensure_ascii=False)
        
        elif "投票" in user_prompt or "vote" in user_prompt.lower():
            # 投票阶段
            target = random.randint(1, 6)
            return json.dumps({
                "thought": f"投票给{target}号，他最可疑",
                "action": {"type": "vote", "target": target}
            }, ensure_ascii=False)
        
        # 默认响应
        return json.dumps({
            "thought": "让我想想...",
            "speech": "我需要更多信息才能做出判断。",
            "action": None
        }, ensure_ascii=False)


class DeepSeekLLM(LLMProviderBase):
    """DeepSeek LLM（备选）"""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = model
    
    async def call(self, system_prompt: str, user_prompt: str) -> str:
        """调用 DeepSeek API"""
        try:
            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=1000
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"❌ API 调用错误: {e}")
            return '{"thought": "API调用失败", "speech": "...", "action": null}'
