"""狼人杀AI对战 - 主程序"""
import asyncio
import os
from game_engine import GameEngine
from llm_provider import QwenLLM, MockLLM


async def main():
    print("="*80)
    print("🎮 狼人杀 AI 对战系统")
    print("="*80)
    print()
    print("配置：6人局（2狼人 + 1预言家 + 1女巫 + 2村民）")
    print()
    
    # 选择LLM
    api_key = os.getenv("QWEN_API_KEY")
    
    if api_key:
        print("✅ 检测到 QWEN_API_KEY，使用通义千问")
        llm = QwenLLM(api_key=api_key)
    else:
        print("⚠️ 未设置 QWEN_API_KEY，使用 MockLLM 测试模式")
        print("   设置方法: export QWEN_API_KEY='你的API密钥'")
        llm = MockLLM()
    
    # 创建游戏引擎
    engine = GameEngine(llm=llm, player_count=6)
    
    # 运行游戏
    await engine.run_game()


if __name__ == "__main__":
    asyncio.run(main())
