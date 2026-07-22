/**
 * Athena Web UI - Main Application
 * Jarvis-inspired AI Assistant Interface
 */

// ==================== Configuration ====================
const CONFIG = {
    wsUrl: `ws://${location.host}/ws/web`,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
    pingInterval: 30000,
};

// ==================== State ====================
const state = {
    connected: false,
    processing: false,
    clientId: `web-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    ws: null,
    reconnectAttempts: 0,
    skills: [],
    stats: {},
    messageId: 0,
};

// ==================== DOM Elements ====================
const els = {
    // Header
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),

    // Chat
    messages: document.getElementById('messages'),
    messagesContainer: document.getElementById('messagesContainer'),
    typingIndicator: document.getElementById('typingIndicator'),
    chatForm: document.getElementById('chatForm'),
    textInput: document.getElementById('textInput'),
    sendBtn: document.getElementById('sendBtn'),
    clearChatBtn: document.getElementById('clearChat'),

    // Side panel
    sidePanel: document.querySelector('.side-panel'),

    // Side panel tabs
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    skillsBtn: document.getElementById('skillsBtn'),
    memoryBtn: document.getElementById('memoryBtn'),
    settingsBtn: document.getElementById('settingsBtn'),

    // Skills
    skillsList: document.getElementById('skillsList'),
    refreshSkillsBtn: document.getElementById('refreshSkills'),
    forgeInput: document.getElementById('forgeInput'),
    forgeBtn: document.getElementById('forgeBtn'),

    // Memory
    memoryQuery: document.getElementById('memoryQuery'),
    searchMemoryBtn: document.getElementById('searchMemory'),
    memoryResults: document.getElementById('memoryResults'),

    // Stats
    statMemory: document.getElementById('statMemory'),
    statSkills: document.getElementById('statSkills'),
    statConversations: document.getElementById('statConversations'),
    statPersona: document.getElementById('statPersona'),
    uptime: document.getElementById('uptime'),
    modelInfo: document.getElementById('modelInfo'),
    modeInfo: document.getElementById('modeInfo'),

    // Modals
    skillModal: document.getElementById('skillModal'),
    closeSkillModal: document.getElementById('closeSkillModal'),
    modalForgeInput: document.getElementById('modalForgeInput'),
    cancelForge: document.getElementById('cancelForge'),
    confirmForge: document.getElementById('confirmForge'),

    // Toast
    toastContainer: document.getElementById('toastContainer'),
};

// ==================== Utility Functions ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Safe Markdown rendering
function renderMarkdown(text) {
    if (!text) return '';
    // Unescape literal unicode escape sequences like \u2019 -> '
    try {
        text = text.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    } catch (e) {}
    try {
        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(text);
        }
    } catch (e) {
        console.warn('[Markdown] Render error:', e);
    }
    return escapeHtml(text);
}

function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatUptime(seconds) {
    if (!seconds) return '--';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function generateId() {
    return `msg-${++state.messageId}-${Date.now()}`;
}

// ==================== Toast Notifications ====================
function showToast(message, type = 'info', title = '') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
    };

    const defaultTitles = { success: 'Success', error: 'Error', info: 'Info' };

    toast.innerHTML = `
        ${icons[type] || icons.info}
        <div class="toast-content">
            <div class="toast-title">${title || defaultTitles[type]}</div>
            <div class="toast-message">${escapeHtml(message)}</div>
        </div>
    `;

    els.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ==================== WebSocket Connection ====================
function connect() {
    if (state.ws?.readyState === WebSocket.OPEN) return;

    state.ws = new WebSocket(CONFIG.wsUrl);

    state.ws.onopen = () => {
        console.log('[WS] Connected');
        state.connected = true;
        state.reconnectAttempts = 0;
        updateConnectionStatus(true);
        showToast('Connected to Athena', 'success');

        // Start ping interval
        startPing();
    };

    state.ws.onclose = () => {
        console.log('[WS] Disconnected');
        state.connected = false;
        updateConnectionStatus(false);

        if (state.reconnectAttempts < CONFIG.maxReconnectAttempts) {
            state.reconnectAttempts++;
            console.log(`[WS] Reconnecting (${state.reconnectAttempts}/${CONFIG.maxReconnectAttempts})...`);
            setTimeout(connect, CONFIG.reconnectInterval);
        } else {
            showToast('Connection lost. Please refresh.', 'error');
        }
    };

    state.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };
}

function startPing() {
    if (state.pingInterval) clearInterval(state.pingInterval);
    state.pingInterval = setInterval(() => {
        if (state.ws?.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'ping' }));
        }
    }, CONFIG.pingInterval);
}

function sendMessage(msg) {
    if (state.ws?.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(msg));
    } else {
        console.warn('[WS] Not connected, queuing message');
    }
}

function updateConnectionStatus(connected) {
    state.connected = connected;
    els.statusIndicator.classList.toggle('connected', connected);
    els.statusText.textContent = connected ? 'Connected' : 'Disconnected';
    els.sendBtn.disabled = !connected;
}

// ==================== Message Handling ====================
function handleMessage(msg) {
    switch (msg.type) {
        case 'welcome':
            console.log('[WS] Welcome:', msg.message);
            if (!state.hasWelcomed) {
                addMessage('assistant', "System initialized. I am Athena, your personal AI assistant. How may I help you?");
                state.hasWelcomed = true;
            }
            break;

        case 'pong':
            break;

        case 'status':
            handleStatus(msg);
            break;

        case 'chat':
            handleChatMessage(msg);
            break;

        case 'assistant_response':
            setProcessing(false);
            addMessage('assistant', msg.text || msg.response);
            break;

        case 'skills':
            renderSkills(msg.skills);
            break;

        case 'skill_forged':
            showToast(msg.message, msg.success ? 'success' : 'error');
            if (msg.success) refreshSkills();
            break;

        case 'memory':
            renderMemoryResults(msg.results);
            break;

        case 'stats':
            updateStats(msg.stats);
            break;

        case 'error':
            showToast(msg.message, 'error', 'Error');
            setProcessing(false);
            break;

        default:
            console.log('[WS] Unknown message:', msg);
    }
}

function handleStatus(msg) {
    if (msg.state === 'processing') {
        setProcessing(true);
    } else if (msg.state === 'idle') {
        setProcessing(false);
    }

    if (msg.message) {
        els.statusText.textContent = msg.message;
    }
}

function handleChatMessage(msg) {
    setProcessing(false);

    if (msg.role === 'assistant') {
        addMessage('assistant', msg.text || msg.response);
    }
}

function setProcessing(processing) {
    state.processing = processing;
    els.typingIndicator.style.display = processing ? 'flex' : 'none';
    els.sendBtn.disabled = processing || !state.connected;
    els.textInput.disabled = processing;

    if (processing) {
        els.statusIndicator.classList.add('processing');
        els.statusIndicator.classList.remove('connected');
        els.statusText.textContent = 'Processing...';
    } else {
        els.statusIndicator.classList.remove('processing');
        els.statusIndicator.classList.add('connected');
        els.statusText.textContent = 'Connected';
    }

    scrollToBottom();
}

// ==================== Chat UI ====================
function addMessage(role, text) {
    if (!text) return;
    const msgId = generateId();
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.id = msgId;

    const avatar = role === 'user' ? '👤' : '🤖';
    const time = formatTime(Date.now() / 1000);
    
    // Parse markdown for assistant, escape for user
    const contentHtml = role === 'assistant' ? renderMarkdown(text) : escapeHtml(text);

    div.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text markdown-body" id="text-${msgId}"></div>
            <div class="message-time">${time}</div>
        </div>
    `;

    els.messages.appendChild(div);
    
    const textContainer = div.querySelector(`#text-${msgId}`);
    
    if (role === 'assistant') {
        textContainer.innerHTML = contentHtml;
        if (window.hljs) {
            textContainer.querySelectorAll('pre code').forEach((block) => {
                try {
                    window.hljs.highlightElement(block);
                } catch (e) {}
            });
        }
    } else {
        textContainer.innerHTML = contentHtml;
    }
    
    scrollToBottom();
}

function scrollToBottom() {
    els.messagesContainer.scrollTop = els.messagesContainer.scrollHeight;
}

// ==================== Skills ====================
function refreshSkills() {
    sendMessage({ type: 'get_skills' });
}

function renderSkills(skills) {
    state.skills = skills || [];
    els.skillsList.innerHTML = '';

    if (!skills || skills.length === 0) {
        els.skillsList.innerHTML = '<p class="empty-state">No skills loaded</p>';
        return;
    }

    skills.forEach(skill => {
        const card = document.createElement('div');
        card.className = 'skill-card';
        
        // Calculate success rate percentage
        const rate = skill.success_rate || 0;
        const ratePercent = Math.round(rate * 100);
        
        card.innerHTML = `
            <div class="skill-header">
                <span class="skill-name">${escapeHtml(skill.name)}</span>
                <div class="skill-meta">
                    <span class="use-count">Used: ${skill.use_count || 0}</span>
                </div>
            </div>
            <div class="skill-desc">${escapeHtml(skill.description || 'No description')}</div>
            <div class="skill-stats">
                <div class="skill-progress-bar">
                    <div class="skill-progress-fill" style="width: ${ratePercent}%"></div>
                </div>
                <span class="skill-rate-text">${ratePercent}% Success</span>
            </div>
            <div class="skill-actions">
                <button class="btn secondary small execute-skill-btn" data-skill="${escapeHtml(skill.name)}">Execute</button>
            </div>
        `;
        els.skillsList.appendChild(card);
    });
    
    // Add execute listeners
    document.querySelectorAll('.execute-skill-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const skillName = e.target.dataset.skill;
            executeSkill(skillName);
        });
    });
}

function executeSkill(name) {
    sendMessage({
        type: 'execute_skill',
        name: name,
        args: {}
    });
    showToast(`Executing ${name}...`, 'info');
}

function forgeSkill(description) {
    sendMessage({
        type: 'forge_skill',
        description: description
    });
    closeModal('skillModal');
}

// ==================== Memory ====================
function searchMemory(query) {
    sendMessage({
        type: 'query_memory',
        query: query,
        limit: 20
    });
}

function renderMemoryResults(results) {
    state.memoryResults = results || [];
    els.memoryResults.innerHTML = '';

    if (!results || results.length === 0) {
        els.memoryResults.innerHTML = '<p class="empty-state">No memories found</p>';
        return;
    }

    results.forEach(mem => {
        const item = document.createElement('div');
        item.className = 'memory-item';
        item.innerHTML = `
            <div class="memory-item-header">
                <span class="memory-type">${escapeHtml(mem.type)}</span>
                <span>${formatTime(mem.created_at)}</span>
            </div>
            <div class="memory-content">${escapeHtml(mem.content)}</div>
        `;
        els.memoryResults.appendChild(item);
    });
}

// ==================== Stats ====================
function updateStats(stats) {
    state.stats = stats || {};

    // Update stat cards
    const mem = stats.memory || {};
    els.statMemory.textContent = `${mem.total_memories || 0} entries (${mem.db_size_mb || 0} MB)`;
    els.statSkills.textContent = stats.skills?.total_skills || 0;
    els.statConversations.textContent = mem.total_conversations || 0;
    els.statPersona.textContent = stats.persona?.mood || 'neutral';

    // System info
    if (stats.session) {
        els.uptime.textContent = formatUptime(stats.session.uptime_seconds);
    }
    if (stats.llm) {
        els.modelInfo.textContent = stats.llm.primary_model || '--';
    }
    els.modeInfo.textContent = 'Web';
}

// ==================== Modal Handling ====================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'flex';
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

// ==================== Side Panel Toggle ====================
function toggleSidePanel() {
    if (els.sidePanel) {
        els.sidePanel.classList.toggle('open');
    }
}

function closeSidePanel() {
    if (els.sidePanel) {
        els.sidePanel.classList.remove('open');
    }
}

// ==================== Tab Handling ====================
function initTabs() {
    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;

            els.tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            els.tabPanes.forEach(p => p.classList.remove('active'));
            document.getElementById(`${tab}Pane`).classList.add('active');

            // Load data for tab
            if (tab === 'skills') refreshSkills();
            else if (tab === 'stats') sendMessage({ type: 'get_stats' });
        });
    });
}

// ==================== Event Listeners ====================
function initEventListeners() {
    // Chat form
    els.chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = els.textInput.value.trim();
        if (!text || state.processing) return;

        addMessage('user', text);
        els.textInput.value = '';
        els.textInput.style.height = 'auto';
        setProcessing(true);

        sendMessage({ type: 'chat', text });
    });
    
    // Handle Enter to submit in textarea
    els.textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            els.chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Auto-resize textarea
    els.textInput.addEventListener('input', () => {
        els.textInput.style.height = 'auto';
        els.textInput.style.height = Math.min(els.textInput.scrollHeight, 160) + 'px';
    });

    // Clear chat
    els.clearChatBtn.addEventListener('click', () => {
        els.messages.innerHTML = '';
    });

    // Side panel toggles
    els.skillsBtn.addEventListener('click', () => openTab('skills'));
    els.memoryBtn.addEventListener('click', () => openTab('memory'));
    els.settingsBtn.addEventListener('click', () => openTab('stats'));

    // Side panel toggle (mobile)
    const sidePanelToggle = document.getElementById('sidePanelToggle');
    if (sidePanelToggle) {
        sidePanelToggle.addEventListener('click', toggleSidePanel);
    }

    function openTab(tab) {
        const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (btn) btn.click();
    }

    // Forge skill
    els.forgeBtn.addEventListener('click', () => {
        const desc = els.forgeInput.value.trim();
        if (desc) {
            forgeSkill(desc);
            els.forgeInput.value = '';
        } else {
            showToast('Enter a skill description', 'error');
        }
    });

    // Modal forge
    els.confirmForge.addEventListener('click', () => {
        const desc = els.modalForgeInput.value.trim();
        if (desc) {
            forgeSkill(desc);
            els.modalForgeInput.value = '';
        }
    });

    els.cancelForge.addEventListener('click', () => closeModal('skillModal'));
    els.closeSkillModal.addEventListener('click', () => closeModal('skillModal'));

    // Memory search
    els.searchMemoryBtn.addEventListener('click', () => {
        const query = els.memoryQuery.value.trim();
        if (query) searchMemory(query);
    });

    els.memoryQuery.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const query = els.memoryQuery.value.trim();
            if (query) searchMemory(query);
        }
    });

    // Refresh skills
    els.refreshSkillsBtn.addEventListener('click', refreshSkills);

    // Modal close on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.style.display = 'none';
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Escape to close modals
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
        }

        // Ctrl/Cmd + K to focus input
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            els.textInput.focus();
        }

        // Ctrl/Cmd + / to show shortcuts (future)
    });
}

// ==================== Initialization ====================
async function init() {
    console.log('[Athena Web] Initializing...');

    initTabs();
    initEventListeners();

    // Connect to WebSocket
    connect();

    // Load initial stats
    setTimeout(() => sendMessage({ type: 'get_stats' }), 1000);

    // Periodic stats update
    setInterval(() => {
        if (state.connected) sendMessage({ type: 'get_stats' });
    }, 10000);

    // Focus input
    els.textInput.focus();

    console.log('[Athena Web] Ready');
}

// ==================== Start ====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}