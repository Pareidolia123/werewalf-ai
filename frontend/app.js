// 狼人杀 AI 对战 - 前端逻辑

class WerewolfGame {
    constructor() {
        this.ws = null;
        this.players = [];
        this.voteCounts = {};
        
        this.initElements();
        this.bindEvents();
    }
    
    initElements() {
        this.btnStart = document.getElementById('btnStart');
        this.btnRestart = document.getElementById('btnRestart');
        this.apiKeyInput = document.getElementById('apiKey');
        this.controlPanel = document.getElementById('controlPanel');
        this.gameStatus = document.getElementById('gameStatus');
        this.roundInfo = document.getElementById('roundInfo');
        this.phaseInfo = document.getElementById('phaseInfo');
        this.playersArea = document.getElementById('playersArea');
        this.logContent = document.getElementById('logContent');
        this.speechDisplay = document.getElementById('speechDisplay');
        this.speakerId = document.getElementById('speakerId');
        this.speechContent = document.getElementById('speechContent');
        this.thoughtContent = document.getElementById('thoughtContent');
        this.gameResult = document.getElementById('gameResult');
        this.resultTitle = document.getElementById('resultTitle');
        this.finalRoles = document.getElementById('finalRoles');
    }
    
    bindEvents() {
        this.btnStart.addEventListener('click', () => this.startGame());
        this.btnRestart.addEventListener('click', () => this.restartGame());
    }
    
    startGame() {
        this.btnStart.disabled = true;
        this.btnStart.textContent = '游戏进行中...';
        this.logContent.innerHTML = '';
        this.voteCounts = {};
        
        // 建立 WebSocket 连接
        const wsUrl = `ws://${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.addLog('🔗 连接服务器成功', 'info');
            // 发送开始游戏命令
            this.ws.send(JSON.stringify({
                action: 'start_game',
                api_key: this.apiKeyInput.value || null
            }));
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        this.ws.onclose = () => {
            this.addLog('🔌 连接已断开', 'info');
            this.btnStart.disabled = false;
            this.btnStart.textContent = '🎮 开始游戏';
        };
        
        this.ws.onerror = (error) => {
            this.addLog('❌ 连接错误', 'error');
            console.error('WebSocket error:', error);
        };
    }
    
    restartGame() {
        this.gameResult.style.display = 'none';
        this.speechDisplay.style.display = 'none';
        this.playersArea.innerHTML = '';
        this.startGame();
    }
    
    handleMessage(message) {
        const { type, data } = message;
        
        switch (type) {
            case 'info':
                this.addLog(data.message, 'info');
                break;
                
            case 'game_start':
                this.onGameStart(data);
                break;
                
            case 'phase_change':
                this.onPhaseChange(data);
                break;
                
            case 'action':
                this.addLog(data.message, 'action');
                break;
                
            case 'death':
                this.onDeath(data);
                break;
                
            case 'speaking':
                this.onSpeaking(data);
                break;
                
            case 'speech':
                this.onSpeech(data);
                break;
                
            case 'vote':
                this.onVote(data);
                break;
                
            case 'vote_result':
                this.onVoteResult(data);
                break;
                
            case 'eliminated':
                this.onEliminated(data);
                break;
                
            case 'game_over':
                this.onGameOver(data);
                break;
        }
    }
    
    onGameStart(data) {
        this.players = data.players;
        this.addLog(data.message, 'phase');
        this.controlPanel.style.display = 'none';
        this.renderPlayers();
    }
    
    onPhaseChange(data) {
        this.roundInfo.textContent = `第 ${data.round} 轮`;
        
        if (data.phase === 'night') {
            this.phaseInfo.textContent = '🌙 夜晚';
            this.phaseInfo.className = 'phase night';
        } else if (data.phase === 'day_speech') {
            this.phaseInfo.textContent = '💬 发言';
            this.phaseInfo.className = 'phase day';
        } else if (data.phase === 'day_vote') {
            this.phaseInfo.textContent = '🗳️ 投票';
            this.phaseInfo.className = 'phase day';
            this.voteCounts = {};
            this.updateVoteBadges();
        }
        
        this.addLog(data.message, 'phase');
        this.speechDisplay.style.display = 'none';
    }
    
    onDeath(data) {
        const player = this.players.find(p => p.id === data.player_id);
        if (player) {
            player.is_alive = false;
        }
        this.renderPlayers();
        this.addLog(data.message, 'death');
    }
    
    onSpeaking(data) {
        // 高亮正在发言的玩家
        document.querySelectorAll('.player-card').forEach(card => {
            card.classList.remove('speaking');
        });
        
        const card = document.getElementById(`player-${data.player_id}`);
        if (card) {
            card.classList.add('speaking');
        }
        
        this.speechDisplay.style.display = 'block';
        this.speakerId.textContent = `${data.player_id}号玩家`;
        this.speechContent.textContent = '思考中...';
        this.thoughtContent.textContent = '';
    }
    
    onSpeech(data) {
        this.speechContent.textContent = `「${data.speech}」`;
        if (data.thought) {
            this.thoughtContent.textContent = data.thought;
            this.thoughtContent.style.display = 'block';
        } else {
            this.thoughtContent.style.display = 'none';
        }
        
        this.addLog(`${data.player_id}号: ${data.speech}`, 'speech');
    }
    
    onVote(data) {
        this.voteCounts[data.target] = (this.voteCounts[data.target] || 0) + 1;
        this.updateVoteBadges();
        this.addLog(data.message, 'vote');
        
        // 动画效果
        const card = document.getElementById(`player-${data.target}`);
        if (card) {
            card.classList.add('voted');
            setTimeout(() => card.classList.remove('voted'), 500);
        }
    }
    
    onVoteResult(data) {
        this.addLog('📊 投票统计:', 'info');
        for (const [playerId, count] of Object.entries(data.counts)) {
            this.addLog(`  ${playerId}号: ${count}票`, 'info');
        }
    }
    
    onEliminated(data) {
        const player = this.players.find(p => p.id === data.player_id);
        if (player) {
            player.is_alive = false;
            player.role = data.role;
        }
        this.renderPlayers();
        this.addLog(data.message, 'death');
        
        // 清除投票徽章
        this.voteCounts = {};
        this.updateVoteBadges();
    }
    
    onGameOver(data) {
        // 更新所有玩家角色信息
        this.players = data.players;
        this.renderPlayers(true);
        
        // 显示结果弹窗
        if (data.winner === 'werewolf') {
            this.resultTitle.textContent = '🐺 狼人阵营胜利！';
        } else {
            this.resultTitle.textContent = '🎉 好人阵营胜利！';
        }
        
        // 显示最终角色
        let rolesHtml = '';
        for (const player of data.players) {
            const deadClass = player.is_alive ? '' : 'dead';
            const status = player.is_alive ? '存活' : '死亡';
            rolesHtml += `
                <div class="final-role-item ${deadClass}">
                    <span>${player.id}号</span>
                    <span>${player.role}</span>
                    <span>${status}</span>
                </div>
            `;
        }
        this.finalRoles.innerHTML = rolesHtml;
        
        this.gameResult.style.display = 'flex';
        this.addLog(data.message, 'phase');
        
        // 关闭 WebSocket
        if (this.ws) {
            this.ws.close();
        }
    }
    
    renderPlayers(showRoles = false) {
        let html = '';
        
        for (const player of this.players) {
            const deadClass = player.is_alive ? '' : 'dead';
            const avatar = this.getAvatar(player.role_key, player.is_alive);
            const roleDisplay = showRoles || !player.is_alive ? player.role : '???';
            
            html += `
                <div class="player-card ${deadClass}" id="player-${player.id}">
                    <div class="player-avatar">${avatar}</div>
                    <div class="player-id">${player.id}号</div>
                    <div class="player-role ${showRoles ? 'revealed' : ''}">${roleDisplay}</div>
                    <div class="player-status">${player.is_alive ? '' : '💀'}</div>
                    <div class="vote-badge" id="vote-${player.id}" style="display: none;">0</div>
                </div>
            `;
        }
        
        this.playersArea.innerHTML = html;
    }
    
    getAvatar(roleKey, isAlive) {
        if (!isAlive) return '💀';
        
        const avatars = {
            'werewolf': '🐺',
            'seer': '🔮',
            'witch': '🧪',
            'villager': '👤'
        };
        
        return avatars[roleKey] || '❓';
    }
    
    updateVoteBadges() {
        // 先隐藏所有
        document.querySelectorAll('.vote-badge').forEach(badge => {
            badge.style.display = 'none';
        });
        
        // 显示有票的
        for (const [playerId, count] of Object.entries(this.voteCounts)) {
            const badge = document.getElementById(`vote-${playerId}`);
            if (badge) {
                badge.textContent = count;
                badge.style.display = 'flex';
            }
        }
    }
    
    addLog(message, type = 'info') {
        const item = document.createElement('p');
        item.className = `log-item ${type}`;
        item.textContent = message;
        this.logContent.appendChild(item);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
}

// 启动游戏
document.addEventListener('DOMContentLoaded', () => {
    new WerewolfGame();
});
