/* ============================================
   PAM GATEWAY — USER PORTAL SPA
   portal.js — Full User Portal Logic
   ============================================ */

const API = '';
let _currentUserId = null;
let _currentUserName = '';
let _allUsers = [];
let _myGrants = [];
let _myRequests = [];
let _availableServers = [];
let _pollInterval = null;
let _currentPage = 'home';

// ─── API Helpers ─────────────────────────────
async function papi(method, path, body, userId) {
    const uid = userId || _currentUserId;
    const headers = { 'Content-Type': 'application/json' };
    // Demo mode: truyền user_id qua header để simulate "current user"
    if (uid) headers['X-Demo-User-Id'] = uid;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
}

// ─── Toast ───────────────────────────────────
function pToast(msg, type = 'info') {
    const c = document.getElementById('pToastContainer');
    if (!c) return;
    const t = document.createElement('div');
    t.className = `p-toast p-toast-${type}`;
    t.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> ${msg}`;
    c.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transition = 'opacity .3s';
        setTimeout(() => t.remove(), 300);
    }, 3500);
}

// ─── Util ────────────────────────────────────
function pFmtDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleString('vi-VN', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

function protocolIcon(p) {
    return { ssh: '🖥️', rdp: '🪟', vnc: '👁️' }[p] || '🖥️';
}

// ─── User Selector ───────────────────────────
async function initUserSelector() {
    _allUsers = await papi('GET', '/auth/users/').catch(() => []);
    const sel = document.getElementById('userSelector');
    if (!sel) return;
    sel.innerHTML = _allUsers.length > 0
        ? _allUsers.map(u => `<option value="${u.id}">${u.username}${u.full_name ? ' ('+u.full_name+')' : ''}</option>`).join('')
        : '<option value="">Chưa có user nào</option>';

    if (_allUsers.length > 0) {
        _currentUserId = _allUsers[0].id;
        _currentUserName = _allUsers[0].username;
    }

    sel.onchange = async function() {
        _currentUserId = this.value;
        const u = _allUsers.find(u => u.id === this.value);
        _currentUserName = u ? u.username : '';
        await refreshData();
        renderPage(_currentPage);
    };
}

// ─── Data Refresh ────────────────────────────
async function refreshData() {
    if (!_currentUserId) return;
    [_myGrants, _myRequests, _availableServers] = await Promise.all([
        fetchMyGrants(),
        fetchMyRequests(),
        fetchAvailableServers()
    ]);
}

async function fetchMyGrants() {
    // Lấy tất cả grants rồi filter theo user vì endpoint /my dùng token
    const all = await papi('GET', '/access/grants/').catch(() => []);
    return all.filter(g => g.user_id === _currentUserId);
}

async function fetchMyRequests() {
    const all = await papi('GET', '/access/requests/').catch(() => []);
    return all.filter(r => r.user_id === _currentUserId);
}

async function fetchAvailableServers() {
    // Lấy tất cả servers (trong demo mode — user thấy tất cả server để xin)
    // Trong prod thật sẽ filter theo GroupServerPolicy
    const allServers = await papi('GET', '/servers/').catch(() => []);
    const allPolicies = await papi('GET', '/policy/group-server/').catch(() => []);
    const allGroups = await papi('GET', '/auth/groups/').catch(() => []);

    // Tìm group của user hiện tại
    const userGroups = allGroups.filter(g =>
        g.users && g.users.some(u => u.id === _currentUserId)
    );
    const userGroupIds = userGroups.map(g => g.id);
    const isAdmin = userGroups.some(g => g.name.includes('Admin'));

    if (isAdmin || allPolicies.length === 0) {
        // Admin hoặc chưa setup policy → thấy tất cả
        return allServers.map(s => ({ ...s, max_duration_minutes: 480, require_approval: true }));
    }

    // Lọc server theo policy của group
    const serverPolicyMap = {};
    allPolicies
        .filter(p => userGroupIds.includes(p.group_id))
        .forEach(p => {
            const sid = p.server_id;
            if (!serverPolicyMap[sid] || p.max_duration_minutes > serverPolicyMap[sid].max_duration_minutes) {
                serverPolicyMap[sid] = { max_duration_minutes: p.max_duration_minutes, require_approval: p.require_approval };
            }
        });

    return allServers
        .filter(s => serverPolicyMap[s.id])
        .map(s => ({ ...s, ...serverPolicyMap[s.id] }));
}

// ─── Polling for pending requests ────────────
function startPolling() {
    stopPolling();
    _pollInterval = setInterval(async () => {
        const hadPending = _myRequests.some(r => r.status === 'pending');
        await refreshData();
        const hasPending = _myRequests.some(r => r.status === 'pending');
        const newApproved = _myRequests.some(r => r.status === 'approved') && _myGrants.length > 0;

        if (hadPending && !hasPending && newApproved) {
            pToast('🎉 Yêu cầu của bạn đã được Admin phê duyệt! Bấm kết nối để truy cập.', 'success');
        }
        renderPage(_currentPage);
    }, 5000);
}

function stopPolling() {
    if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
}

// ─── Router ──────────────────────────────────
function renderPage(page) {
    _currentPage = page;
    document.querySelectorAll('.topbar-btn').forEach(b => b.classList.toggle('active', b.dataset.page === page));
    const content = document.getElementById('portalContent');
    if (!content) return;

    switch(page) {
        case 'home': renderHome(content); break;
        case 'servers': renderServers(content); break;
        case 'requests': renderRequests(content); break;
    }
}

// ─── PAGE: Home / My Access ──────────────────
function renderHome(el) {
    const pendingCount = _myRequests.filter(r => r.status === 'pending').length;
    const approvedCount = _myRequests.filter(r => r.status === 'approved').length;
    const activeGrants = _myGrants;

    // Nếu có pending request → bắt đầu polling
    if (pendingCount > 0) {
        startPolling();
    } else {
        stopPolling();
    }

    el.innerHTML = `
        <div class="page-header">
            <h1>👋 Xin chào, <span style="color:var(--p-blue-light)">${_currentUserName || 'Người dùng'}</span>!</h1>
            <p>Quản lý quyền truy cập máy chủ của bạn từ đây.</p>
        </div>

        <div class="portal-stats">
            <div class="portal-stat">
                <div class="ps-icon blue">🖥️</div>
                <div>
                    <div class="ps-value" style="color:var(--p-blue-light)">${_availableServers.length}</div>
                    <div class="ps-label">Server có thể xin</div>
                </div>
            </div>
            <div class="portal-stat">
                <div class="ps-icon green">⚡</div>
                <div>
                    <div class="ps-value" style="color:var(--p-green)">${activeGrants.length}</div>
                    <div class="ps-label">Quyền đang hoạt động</div>
                </div>
            </div>
            <div class="portal-stat">
                <div class="ps-icon yellow">⏳</div>
                <div>
                    <div class="ps-value" style="color:var(--p-yellow)">${pendingCount}</div>
                    <div class="ps-label">Đang chờ duyệt</div>
                </div>
            </div>
            <div class="portal-stat">
                <div class="ps-icon purple">📋</div>
                <div>
                    <div class="ps-value" style="color:var(--p-purple)">${_myRequests.length}</div>
                    <div class="ps-label">Tổng yêu cầu đã gửi</div>
                </div>
            </div>
        </div>

        ${activeGrants.length > 0 ? `
            <div class="section-title">⚡ Quyền đang hoạt động — Bấm kết nối ngay!</div>
            ${activeGrants.map(g => renderGrantCard(g)).join('')}
        ` : ''}

        ${pendingCount > 0 ? `
            <div class="pending-waiting">
                <div class="pw-icon">⏳</div>
                <h3>Đang chờ Admin phê duyệt...</h3>
                <p>Bạn có ${pendingCount} yêu cầu đang chờ duyệt. Trang sẽ tự động cập nhật khi có thay đổi.</p>
                <div style="margin-top:10px">
                    <span class="refresh-indicator">
                        <span class="refresh-dot"></span>
                        Tự động làm mới mỗi 5 giây
                    </span>
                </div>
            </div>
        ` : ''}

        ${activeGrants.length === 0 && pendingCount === 0 ? `
            <div class="card" style="background:var(--p-bg-card);border:1px solid var(--p-border);border-radius:var(--p-radius-lg);padding:32px;text-align:center;margin-bottom:24px;">
                <div style="font-size:48px;margin-bottom:16px;opacity:.5">🔒</div>
                <h3 style="font-size:16px;font-weight:700;color:var(--p-text-sub);margin-bottom:8px">Bạn chưa có quyền truy cập nào</h3>
                <p style="font-size:13px;color:var(--p-text-muted);margin-bottom:20px">Xin quyền từ danh sách máy chủ bên dưới.</p>
                <button class="request-btn" onclick="setPage('servers')">🖥️ Xem danh sách Server</button>
            </div>
        ` : ''}

        ${_myRequests.length > 0 ? `
            <div class="section-title">📋 Yêu cầu gần đây của bạn</div>
            ${_myRequests.slice(0, 5).map(r => renderRequestItem(r)).join('')}
            ${_myRequests.length > 5 ? `<p style="text-align:center;margin-top:10px"><button class="p-btn p-btn-ghost" onclick="setPage('requests')">Xem tất cả ${_myRequests.length} yêu cầu →</button></p>` : ''}
        ` : ''}
    `;

    // Bắt countdown timer
    startGrantTimers();
}

// ─── Grant Card ──────────────────────────────
function renderGrantCard(g) {
    const allServers = _availableServers;
    const server = allServers.find(s => s.id === g.server_id);
    const serverName = server ? server.name : g.server_id;
    const protocol = server ? server.protocol : 'ssh';
    const host = server ? (server.ip || server.host) : '';
    const port = server ? server.port : '';
    const connId = server ? server.guacamole_connection_id : '';

    const expiresAt = new Date(g.expires_at).getTime();
    const remainMs = Math.max(0, expiresAt - Date.now());
    const totalSecs = Math.floor(remainMs / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    const urgent = mins < 5;

    // Build Guacamole URL
    const guacUrl = `/guacamole/#/client/${btoa(`${connId}\0c\0postgresql`)}`;

    return `
        <div class="grant-card">
            <div class="grant-card-top">
                <div class="grant-card-info">
                    <h3>${protocolIcon(protocol)} ${serverName}</h3>
                    <div class="gc-meta">
                        <span>📡 ${host}:${port}</span>
                        <span>🔑 ${protocol.toUpperCase()}</span>
                        <span>📅 Cấp lúc ${pFmtDate(g.granted_at)}</span>
                        <span>⏰ Hết hạn ${pFmtDate(g.expires_at)}</span>
                    </div>
                </div>
                <div class="gc-timer">
                    <div class="timer-label">Thời gian còn lại</div>
                    <div class="timer-value ${urgent ? 'urgent' : ''}" data-expires="${g.expires_at}">${mins}m ${secs < 10 ? '0' : ''}${secs}s</div>
                </div>
            </div>
            <a href="${guacUrl}" target="_blank" class="connect-btn" onclick="pToast('Đang mở kết nối ${protocol.toUpperCase()} đến ${serverName}...','info')">
                <span class="btn-icon">🔗</span>
                Kết nối ${protocol.toUpperCase()} — ${serverName}
            </a>
            <span style="margin-left:12px;font-size:12px;color:var(--p-text-muted)">Sẽ tự động thu hồi khi hết hạn</span>
        </div>
    `;
}

// ─── Request Item ─────────────────────────────
function renderRequestItem(r) {
    const allServers = _availableServers;
    const server = allServers.find(s => s.id === r.server_id);
    const serverName = server ? server.name : r.server_id;
    const protocol = server ? server.protocol : 'ssh';

    return `
        <div class="request-item">
            <div class="ri-status-dot ${r.status}"></div>
            <div class="ri-info">
                <div class="ri-title">${protocolIcon(protocol)} ${serverName} — <span style="color:var(--p-cyan)">${r.requested_minutes} phút</span></div>
                <div class="ri-meta">
                    <span>📅 ${pFmtDate(r.requested_at)}</span>
                </div>
                <div class="ri-reason">"${r.reason}"</div>
            </div>
            <div class="ri-status">
                <span class="p-status-badge ${r.status}">
                    ${{ pending:'⏳ Chờ duyệt', approved:'✅ Đã duyệt', rejected:'❌ Từ chối', expired:'⌛ Hết hạn' }[r.status] || r.status}
                </span>
            </div>
        </div>
    `;
}

// ─── PAGE: Servers ────────────────────────────
function renderServers(el) {
    // Lấy server ids đang có grant
    const activeServerIds = _myGrants.map(g => g.server_id);

    el.innerHTML = `
        <div class="page-header">
            <h1>🖥️ Danh sách Máy chủ</h1>
            <p>Chọn máy chủ bạn muốn truy cập và gửi yêu cầu cho Admin.</p>
        </div>

        ${_availableServers.length === 0 ? `
            <div class="p-empty">
                <div class="e-icon">🔒</div>
                <h3>Chưa có server nào</h3>
                <p>Admin chưa cấu hình server hoặc chưa gán policy cho nhóm của bạn.</p>
            </div>
        ` : `
            <div class="servers-grid">
                ${_availableServers.map(s => {
                    const hasGrant = activeServerIds.includes(s.id);
                    const hasPending = _myRequests.some(r => r.server_id === s.id && r.status === 'pending');
                    const grant = _myGrants.find(g => g.server_id === s.id);

                    return `
                    <div class="server-card ${hasGrant ? 'has-active-grant' : ''}">
                        <div class="sc-header">
                            <div>
                                <div class="sc-protocol-icon ${s.protocol}">${protocolIcon(s.protocol)}</div>
                            </div>
                            ${hasGrant ? `<span class="p-badge p-badge-active">⚡ Đang có quyền</span>` : ''}
                            ${hasPending ? `<span class="p-badge p-badge-approval">⏳ Đang chờ duyệt</span>` : ''}
                        </div>
                        <div class="sc-name">${s.name}</div>
                        <div class="sc-host">${s.ip || s.host || ''}:${s.port}</div>
                        <div class="sc-badges" style="margin-top:10px">
                            <span class="p-badge p-badge-${s.protocol}">${s.protocol.toUpperCase()}</span>
                            ${s.require_approval
                                ? `<span class="p-badge p-badge-approval">🔐 Cần Admin duyệt</span>`
                                : `<span class="p-badge p-badge-auto">⚡ Tự động cấp</span>`
                            }
                            <span class="p-badge p-badge-duration">⏱️ Tối đa ${s.max_duration_minutes || 60} phút</span>
                        </div>
                        <div class="sc-footer" style="margin-top:14px">
                            <div class="sc-duration">Tối đa <strong>${s.max_duration_minutes || 60} phút</strong></div>
                            ${hasGrant
                                ? `<a href="/guacamole/#/client/${btoa((s.guacamole_connection_id||'1')+'\0c\0postgresql')}" target="_blank" class="connect-btn" style="padding:8px 16px;font-size:13px">🔗 Kết nối</a>`
                                : hasPending
                                    ? `<button class="request-btn" disabled>⏳ Đang chờ duyệt...</button>`
                                    : `<button class="request-btn" onclick="showRequestForm('${s.id}','${s.name}','${s.protocol}',${s.max_duration_minutes||60})">📨 Xin quyền</button>`
                            }
                        </div>
                    </div>`;
                }).join('')}
            </div>
        `}
    `;
}

// ─── PAGE: My Requests ────────────────────────
function renderRequests(el) {
    const sorted = _myRequests.slice().reverse();

    el.innerHTML = `
        <div class="page-header">
            <h1>📋 Yêu cầu của tôi</h1>
            <p>Theo dõi trạng thái tất cả yêu cầu xin quyền truy cập của bạn.</p>
        </div>

        ${sorted.length === 0 ? `
            <div class="p-empty">
                <div class="e-icon">📋</div>
                <h3>Chưa có yêu cầu nào</h3>
                <p>Bạn chưa gửi yêu cầu xin quyền nào. <button onclick="setPage('servers')" class="p-btn p-btn-primary" style="margin-top:12px;display:inline-flex">🖥️ Xem Server</button></p>
            </div>
        ` : sorted.map(r => {
            const allServers = _availableServers;
            const server = allServers.find(s => s.id === r.server_id);
            const serverName = server ? server.name : r.server_id;
            const protocol = server ? server.protocol : 'ssh';
            const grant = _myGrants.find(g => g.request_id === r.id);

            return `
            <div class="request-item" style="flex-direction:column;align-items:flex-start;gap:12px">
                <div style="display:flex;align-items:center;gap:16px;width:100%">
                    <div class="ri-status-dot ${r.status}"></div>
                    <div class="ri-info" style="flex:1">
                        <div class="ri-title">${protocolIcon(protocol)} <strong>${serverName}</strong> — <span style="color:var(--p-cyan)">${r.requested_minutes} phút</span></div>
                        <div class="ri-meta">
                            <span>📅 Gửi: ${pFmtDate(r.requested_at)}</span>
                            ${grant ? `<span>✅ Cấp lúc: ${pFmtDate(grant.granted_at)}</span>` : ''}
                            ${grant ? `<span>⏰ Hết hạn: ${pFmtDate(grant.expires_at)}</span>` : ''}
                        </div>
                        <div class="ri-reason">"${r.reason}"</div>
                    </div>
                    <div class="ri-status">
                        <span class="p-status-badge ${r.status}">
                            ${{ pending:'⏳ Chờ duyệt', approved:'✅ Đã duyệt', rejected:'❌ Từ chối', expired:'⌛ Hết hạn' }[r.status] || r.status}
                        </span>
                    </div>
                </div>
                ${grant ? `
                    <a href="/guacamole/#/client/${btoa((server?.guacamole_connection_id||'1')+'\0c\0postgresql')}" target="_blank" class="connect-btn" style="padding:8px 20px;font-size:13px" onclick="pToast('Đang mở kết nối...','info')">
                        🔗 Kết nối ${protocol.toUpperCase()} — ${serverName}
                    </a>
                ` : ''}
            </div>`;
        }).join('')}
    `;
}

// ─── Request Form Modal ───────────────────────
window.showRequestForm = function(serverId, serverName, protocol, maxMinutes) {
    const overlay = document.getElementById('pModalOverlay');
    if (!overlay) return;

    document.getElementById('pModalTitle').textContent = `📨 Xin quyền truy cập`;
    document.getElementById('pModalSubtitle').textContent = `${protocolIcon(protocol)} ${serverName}`;

    const options = [];
    const steps = [15, 30, 60, 90, 120, 180, 240, 360, 480].filter(v => v <= maxMinutes);
    if (steps.length === 0) steps.push(maxMinutes);
    steps.forEach(v => options.push(`<option value="${v}" ${v === Math.min(60, maxMinutes) ? 'selected' : ''}>${v} phút${v === 60 ? ' (khuyến nghị)' : ''}</option>`));

    document.getElementById('pModalBody').innerHTML = `
        <div class="p-form-group">
            <label>Thời gian cần truy cập</label>
            <select class="p-form-control" id="reqMinutes">${options.join('')}</select>
        </div>
        <div class="p-form-group">
            <label>Lý do xin quyền <span style="color:var(--p-red)">*</span></label>
            <textarea class="p-form-control" id="reqReason" placeholder="Mô tả rõ lý do bạn cần truy cập máy chủ này..."></textarea>
        </div>
        <div style="background:rgba(59,130,246,.06);border:1px solid rgba(59,130,246,.15);border-radius:var(--p-radius);padding:10px 14px;font-size:12px;color:var(--p-text-muted)">
            ℹ️ Sau khi gửi, Admin sẽ xem xét và phê duyệt yêu cầu. Bạn sẽ thấy nút kết nối ngay khi được duyệt.
        </div>
    `;

    document.getElementById('pModalFooter').innerHTML = `
        <button class="p-btn p-btn-ghost" onclick="hidePModal()">Hủy</button>
        <button class="p-btn p-btn-primary" onclick="submitRequest('${serverId}', '${serverName}')">📨 Gửi yêu cầu</button>
    `;

    overlay.classList.add('show');
};

window.submitRequest = async function(serverId, serverName) {
    const reason = document.getElementById('reqReason')?.value?.trim();
    const minutes = parseInt(document.getElementById('reqMinutes')?.value);

    if (!reason) { pToast('Vui lòng nhập lý do xin quyền', 'error'); return; }

    try {
        await papi('POST', '/access/requests/', {
            user_id: _currentUserId,
            server_id: serverId,
            reason,
            requested_minutes: minutes
        });

        hidePModal();
        pToast(`✅ Đã gửi yêu cầu xin quyền vào "${serverName}" — Đang chờ Admin duyệt!`, 'success');
        await refreshData();
        renderPage(_currentPage);
        startPolling();
    } catch (e) {
        pToast(e.message, 'error');
    }
};

window.hidePModal = function() {
    document.getElementById('pModalOverlay')?.classList.remove('show');
};

// ─── Grant Countdown Timers ───────────────────
function startGrantTimers() {
    setInterval(() => {
        document.querySelectorAll('.timer-value[data-expires]').forEach(el => {
            const expiresAt = new Date(el.dataset.expires).getTime();
            const remainMs = Math.max(0, expiresAt - Date.now());
            const totalSecs = Math.floor(remainMs / 1000);
            const mins = Math.floor(totalSecs / 60);
            const secs = totalSecs % 60;
            el.textContent = `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
            el.classList.toggle('urgent', mins < 5);
        });
    }, 1000);
}

// ─── Navigation ───────────────────────────────
window.setPage = function(page) {
    renderPage(page);
};

// ─── Init ────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Setup modal close
    const overlay = document.getElementById('pModalOverlay');
    if (overlay) {
        overlay.onclick = (e) => { if (e.target === overlay) hidePModal(); };
    }

    // Setup nav
    document.querySelectorAll('.topbar-btn[data-page]').forEach(btn => {
        btn.onclick = () => setPage(btn.dataset.page);
    });

    // Init user selector
    await initUserSelector();

    // Load data
    await refreshData();

    // Render home
    renderPage('home');

    // Auto-start polling if has pending
    if (_myRequests.some(r => r.status === 'pending')) {
        startPolling();
    }
});
