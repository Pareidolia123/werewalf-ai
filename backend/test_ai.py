"""测试AI玩家响应"""
import asyncio
from models import Player, GameState, PublicEvent, Role, Phase, Personality
from ai_player import AIPlayer
from llm_provider import QwenLLM


def create_test_game_state() -> tuple[GameState, list[Player]]:
    """创建测试用的游戏状态"""
    
    players = [
        Player(id=1, role=Role.WEREWOLF, personality=Personality.AGGRESSIVE, 
               teammates=[2]),
        Player(id=2, role=Role.WEREWOLF, personality=Personality.CUNNING,
               teammates=[1]),
        Player(id=3, role=Role.SEER, personality=Personality.CONSERVATIVE,
               investigated={1: False}),  # 已查验1号是狼人
        Player(id=4, role=Role.WITCH, personality=Personality.CUNNING),
        Player(id=5, role=Role.VILLAGER, personality=Personality.AGGRESSIVE),
        Player(id=6, role=Role.VILLAGER, personality=Personality.CONSERVATIVE),
    ]
    
    game_state = GameState(
        round=1,
        phase=Phase.DAY_SPEECH,
        players=players,
        public_history=[
            PublicEvent(round=1, phase="night", event_type="death", 
                       player_id=5, content="被狼人击杀"),
        ]
    )
    
    players[4].is_alive = False  # 5号已死亡
    
    return game_state, players


async def test_speech():
    """测试发言"""
    print("\n" + "="*80)
    print("🧪 测试场景：第1轮白天发言（5号被狼人杀死）")
    print("="*80)
    
    game_state, players = create_test_game_state()
    
    # ========== 使用真实的通义千问 ==========
    llm = QwenLLM(
        api_key="sk-2f171ed5cf8340c0a9886027eb32147a"  # 替换成你的真实 API Key
    )
    
    # 测试预言家（3号）发言
    seer = players[2]
    ai_player = AIPlayer(seer, llm)
    
    print(f"\n📢 测试 {seer.id}号 ({seer.role.value}) 发言...")
    response = await ai_player.act(game_state, "speech")
    
    print(f"\n{'='*60}")
    print("✅ AI响应结果：")
    print(f"{'='*60}")
    print(f"💭 内心独白: {response.thought}")
    print(f"📣 公开发言: {response.speech}")


async def main():
    print("🎮 狼人杀AI测试 - 使用通义千问")
    print("="*80)
    
    await test_speech()
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
