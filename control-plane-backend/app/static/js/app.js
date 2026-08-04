/* ============================================
   PAM GATEWAY — ADMIN DASHBOARD SPA
   app.js — Full Single Page Application Logic
   ============================================ */

const API = '';  // Same origin

// ── Utility ──────────────────────────────────
async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
}

function toast(msg, type = 'info') {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> ${msg}`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

function shortId(uuid) { return uuid ? uuid.substring(0, 8) + '…' : '—'; }

function fmtDate(d) {
    if (!d) return '—';
    const dt = new Date(d);
    return dt.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function badge(text, type) { return `<span class="badge badge-${type}">${text}</span>`; }

function statusBadge(s) {
    const m = { pending: 'pending', approved: 'approved', rejected: 'rejected', expired: 'expired', active: 'active' };
    return badge(s, m[s] || 'expired');
}

function protocolBadge(p) { return badge(p.toUpperCase(), p); }

function groupBadge(name) {
    if (name.includes('Admin')) return badge(name, 'admin');
    if (name.includes('Support')) return badge(name, 'support');
    if (name.includes('Audit')) return badge(name, 'auditor');
    return badge(name, 'support');
}

// ── Modal ────────────────────────────────────
function showModal(title, bodyHtml, footerHtml) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = bodyHtml;
    document.getElementById('modalFooter').innerHTML = footerHtml || '';
    document.getElementById('modalOverlay').classList.add('show');
}

function hideModal() { document.getElementById('modalOverlay').classList.remove('show'); }

document.getElementById('modalClose').onclick = hideModal;
document.getElementById('modalOverlay').onclick = (e) => { if (e.target.id === 'modalOverlay') hideModal(); };

// ── Data Cache ───────────────────────────────
let _users = [], _groups = [], _servers = [], _policies = [], _requests = [], _grants = [], _sessions = [], _auditLogs = [];

async function loadAll() {
    try {
        [_users, _groups, _servers, _policies, _requests, _grants, _sessions, _auditLogs] = await Promise.all([
            api('GET', '/auth/users/').catch(() => []),
            api('GET', '/auth/groups/').catch(() => []),
            api('GET', '/servers/').catch(() => []),
            api('GET', '/policy/group-server/').catch(() => []),
            api('GET', '/access/requests/').catch(() => []),
            api('GET', '/access/grants/').catch(() => []),
            api('GET', '/audit/sessions/').catch(() => []),
            api('GET', '/audit/logs/').catch(() => [])
        ]);
    } catch (e) { console.error('Load error:', e); }
}

function userName(id) { const u = _users.find(u => u.id === id); return u ? u.username : shortId(id); }
function serverName(id) { const s = _servers.find(s => s.id === id); return s ? s.name : shortId(id); }
function groupName(id) { const g = _groups.find(g => g.id === id); return g ? g.name : shortId(id); }

// ── Router ───────────────────────────────────
const pages = {
    dashboard: { title: 'Dashboard', render: renderDashboard },
    users: { title: 'Quản lý Người dùng', render: renderUsers },
    groups: { title: 'Quản lý Nhóm', render: renderGroups },
    servers: { title: 'Quản lý Máy chủ', render: renderServers },
    policies: { title: 'Chính sách Phân quyền', render: renderPolicies },
    requests: { title: 'Xin Quyền Truy Cập', render: renderRequests },
    approvals: { title: 'Phê Duyệt Yêu Cầu', render: renderApprovals },
    grants: { title: 'Quyền Đang Hoạt Động', render: renderGrants },
    audit: { title: 'Audit Trail', render: renderAudit }
};

async function navigate() {
    const hash = location.hash.slice(1) || 'dashboard';
    const page = pages[hash];
    if (!page) return;

    document.getElementById('pageTitle').textContent = page.title;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.toggle('active', l.dataset.page === hash));
    document.getElementById('contentArea').innerHTML = '<div class="loading-center"><div class="spinner"></div> Đang tải...</div>';

    await loadAll();
    page.render();
}

window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', () => { if (!location.hash) location.hash = '#dashboard'; navigate(); });

// Mobile menu
document.getElementById('menuToggle').onclick = () => document.getElementById('sidebar').classList.toggle('open');

// ── PAGE: Dashboard ──────────────────────────
function renderDashboard() {
    const pending = _requests.filter(r => r.status === 'pending').length;
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-icon">👤</div><div class="stat-value">${_users.length}</div><div class="stat-label">Người dùng</div></div>
            <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-value">${_groups.length}</div><div class="stat-label">Nhóm</div></div>
            <div class="stat-card"><div class="stat-icon">🖥️</div><div class="stat-value">${_servers.length}</div><div class="stat-label">Máy chủ</div></div>
            <div class="stat-card"><div class="stat-icon">🔐</div><div class="stat-value">${_policies.length}</div><div class="stat-label">Chính sách</div></div>
            <div class="stat-card"><div class="stat-icon">⏳</div><div class="stat-value">${pending}</div><div class="stat-label">Chờ duyệt</div></div>
            <div class="stat-card"><div class="stat-icon">⚡</div><div class="stat-value">${_grants.length}</div><div class="stat-label">Quyền hoạt động</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div class="card">
                <div class="card-header"><h3>📋 Yêu cầu gần đây</h3></div>
                <div class="card-body table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Trạng thái</th><th>Thời gian</th></tr></thead>
                    <tbody>${_requests.slice(-5).reverse().map(r => `<tr><td>${userName(r.user_id)}</td><td>${serverName(r.server_id)}</td><td>${statusBadge(r.status)}</td><td>${fmtDate(r.requested_at)}</td></tr>`).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">Chưa có yêu cầu</td></tr>'}</tbody></table>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><h3>⚡ Quyền đang hoạt động</h3></div>
                <div class="card-body table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Hết hạn</th></tr></thead>
                    <tbody>${_grants.map(g => `<tr><td>${userName(g.user_id)}</td><td>${serverName(g.server_id)}</td><td>${fmtDate(g.expires_at)}</td></tr>`).join('') || '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">Không có quyền đang hoạt động</td></tr>'}</tbody></table>
                </div>
            </div>
        </div>
    `;
}

// ── PAGE: Users ──────────────────────────────
function renderUsers() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>👤 Danh sách Người dùng (${_users.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateUserForm()">+ Thêm User</button>
            </div>
            <div class="card-body table-wrapper">
                <table><thead><tr><th>Username</th><th>Email</th><th>Họ tên</th><th>Nhóm</th><th>Trạng thái</th><th>Hành động</th></tr></thead>
                <tbody>${_users.map(u => {
                    const userGroups = _groups.filter(g => g.users && g.users.some(gu => gu.id === u.id));
                    return `<tr>
                        <td><strong>${u.username}</strong></td>
                        <td>${u.email || '—'}</td>
                        <td>${u.full_name || '—'}</td>
                        <td><div class="group-pills">${userGroups.length > 0 ? userGroups.map(g => groupBadge(g.name)).join('') : '<span style="color:var(--text-muted)">Chưa gán nhóm</span>'}</div></td>
                        <td>${u.is_active ? badge('Active', 'active') : badge('Inactive', 'expired')}</td>
                        <td><button class="btn btn-ghost btn-sm" onclick="showAssignGroupModal('${u.id}', '${u.username}')">Gán nhóm</button></td>
                    </tr>`;
                }).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.showCreateUserForm = function() {
    showModal('Thêm Người dùng mới', `
        <div class="form-group"><label>Username</label><input class="form-control" id="newUsername" placeholder="Nhập username"></div>
        <div class="form-group"><label>Email</label><input class="form-control" id="newEmail" type="email" placeholder="Nhập email"></div>
        <div class="form-group"><label>Họ tên đầy đủ</label><input class="form-control" id="newFullName" placeholder="Nhập họ tên"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="createUser()">Tạo User</button>`);
};

window.createUser = async function() {
    try {
        await api('POST', '/auth/users/', {
            username: document.getElementById('newUsername').value,
            email: document.getElementById('newEmail').value || null,
            full_name: document.getElementById('newFullName').value || null
        });
        hideModal(); toast('Đã tạo User thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.showAssignGroupModal = function(userId, username) {
    const opts = _groups.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
    showModal(`Gán nhóm cho "${username}"`, `
        <div class="form-group"><label>Chọn nhóm</label><select class="form-control" id="assignGroupId">${opts}</select></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="assignGroup('${userId}')">Gán nhóm</button>`);
};

window.assignGroup = async function(userId) {
    try {
        const gid = document.getElementById('assignGroupId').value;
        await api('POST', `/auth/users/${userId}/groups/${gid}`);
        hideModal(); toast('Đã gán nhóm thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Groups ─────────────────────────────
function renderGroups() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>👥 Danh sách Nhóm (${_groups.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateGroupForm()">+ Tạo nhóm</button>
            </div>
            <div class="card-body table-wrapper">
                <table><thead><tr><th>Tên nhóm</th><th>Mô tả</th><th>Số thành viên</th><th>Chính sách Server</th></tr></thead>
                <tbody>${_groups.map(g => {
                    const memberCount = g.users ? g.users.length : 0;
                    const gPolicies = _policies.filter(p => p.group_id === g.id);
                    return `<tr>
                        <td>${groupBadge(g.name)}</td>
                        <td>${g.description || '—'}</td>
                        <td><strong>${memberCount}</strong> user</td>
                        <td>${gPolicies.length > 0 ? gPolicies.map(p => `<span class="tag">${serverName(p.server_id)} (${p.max_duration_minutes}p)</span>`).join('') : '<span style="color:var(--text-muted)">Chưa gán</span>'}</td>
                    </tr>`;
                }).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.showCreateGroupForm = function() {
    showModal('Tạo Nhóm mới', `
        <div class="form-group"><label>Tên nhóm</label><input class="form-control" id="newGroupName" placeholder="VD: PAM-DevOps"></div>
        <div class="form-group"><label>Mô tả</label><input class="form-control" id="newGroupDesc" placeholder="Mô tả nhóm"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="createGroup()">Tạo nhóm</button>`);
};

window.createGroup = async function() {
    try {
        await api('POST', '/auth/groups/', { name: document.getElementById('newGroupName').value, description: document.getElementById('newGroupDesc').value || null });
        hideModal(); toast('Đã tạo Nhóm thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Servers ────────────────────────────
function renderServers() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>🖥️ Danh sách Máy chủ (${_servers.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateServerForm()">+ Thêm Server</button>
            </div>
            <div class="card-body table-wrapper">
                <table><thead><tr><th>Tên</th><th>Giao thức</th><th>Địa chỉ</th><th>Cổng</th><th>Connection ID</th><th>Hành động</th></tr></thead>
                <tbody>${_servers.map(s => `<tr>
                    <td><strong>${s.name}</strong></td>
                    <td>${protocolBadge(s.protocol)}</td>
                    <td>${s.host}</td>
                    <td>${s.port}</td>
                    <td><span class="tag">#${s.guacamole_connection_id}</span></td>
                    <td><button class="btn btn-danger btn-sm" onclick="deleteServer('${s.id}')">Xóa</button></td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.showCreateServerForm = function() {
    showModal('Thêm Máy chủ mới', `
        <div class="form-group"><label>Tên hiển thị</label><input class="form-control" id="srvName" placeholder="VD: Linux Production"></div>
        <div class="form-row">
            <div class="form-group"><label>Giao thức</label><select class="form-control" id="srvProtocol"><option value="ssh">SSH</option><option value="vnc">VNC</option><option value="rdp">RDP</option></select></div>
            <div class="form-group"><label>Cổng</label><input class="form-control" id="srvPort" type="number" value="22"></div>
        </div>
        <div class="form-group"><label>Địa chỉ Host</label><input class="form-control" id="srvHost" placeholder="VD: 192.168.1.100"></div>
        <div class="form-group"><label>Guacamole Connection ID</label><input class="form-control" id="srvConnId" placeholder="VD: 1"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="createServer()">Thêm Server</button>`);
};

window.createServer = async function() {
    try {
        await api('POST', '/servers/', {
            name: document.getElementById('srvName').value,
            host: document.getElementById('srvHost').value,
            port: parseInt(document.getElementById('srvPort').value),
            protocol: document.getElementById('srvProtocol').value,
            guacamole_connection_id: document.getElementById('srvConnId').value
        });
        hideModal(); toast('Đã thêm Server thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.deleteServer = async function(id) {
    if (!confirm('Bạn có chắc muốn xóa Server này?')) return;
    try { await api('DELETE', `/servers/${id}`); toast('Đã xóa Server.', 'success'); navigate(); } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Policies ───────────────────────────
function renderPolicies() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card" style="margin-bottom:16px;">
            <div class="card-header">
                <h3>🔐 Tạo Chính sách mới</h3>
            </div>
            <div class="card-body">
                <div class="form-row">
                    <div class="form-group"><label>Nhóm</label><select class="form-control" id="polGroup">${_groups.map(g => `<option value="${g.id}">${g.name}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Máy chủ</label><select class="form-control" id="polServer">${_servers.map(s => `<option value="${s.id}">${s.name} (${s.protocol.toUpperCase()})</option>`).join('')}</select></div>
                    <div class="form-group"><label>Thời lượng tối đa (phút)</label><input class="form-control" id="polMaxMin" type="number" value="60"></div>
                    <div class="form-group"><label>Yêu cầu phê duyệt</label><select class="form-control" id="polApproval"><option value="true">Bắt buộc duyệt</option><option value="false">Tự động cấp</option></select></div>
                </div>
                <button class="btn btn-primary" onclick="createPolicy()">+ Tạo chính sách</button>
            </div>
        </div>
        <div class="card">
            <div class="card-header"><h3>📋 Danh sách Chính sách (${_policies.length})</h3></div>
            <div class="card-body table-wrapper">
                <table><thead><tr><th>Nhóm</th><th>Máy chủ</th><th>Thời lượng tối đa</th><th>Phê duyệt</th><th>Ngày tạo</th><th>Hành động</th></tr></thead>
                <tbody>${_policies.map(p => `<tr>
                    <td>${groupBadge(groupName(p.group_id))}</td>
                    <td><strong>${serverName(p.server_id)}</strong></td>
                    <td>${p.max_duration_minutes} phút</td>
                    <td>${p.require_approval ? badge('Bắt buộc', 'pending') : badge('Tự động', 'active')}</td>
                    <td>${fmtDate(p.created_at)}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deletePolicy('${p.id}')">Xóa</button></td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.createPolicy = async function() {
    try {
        await api('POST', '/policy/group-server/', {
            group_id: document.getElementById('polGroup').value,
            server_id: document.getElementById('polServer').value,
            max_duration_minutes: parseInt(document.getElementById('polMaxMin').value),
            require_approval: document.getElementById('polApproval').value === 'true'
        });
        toast('Đã tạo chính sách thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.deletePolicy = async function(id) {
    if (!confirm('Xóa chính sách này?')) return;
    try { await api('DELETE', `/policy/group-server/${id}`); toast('Đã xóa chính sách.', 'success'); navigate(); } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Requests (Xin quyền) ───────────────
function renderRequests() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card" style="margin-bottom:16px;">
            <div class="card-header"><h3>📋 Gửi Yêu Cầu Truy Cập</h3></div>
            <div class="card-body">
                <div class="form-row">
                    <div class="form-group"><label>Người dùng</label><select class="form-control" id="reqUser">${_users.map(u => `<option value="${u.id}">${u.username}${u.full_name ? ' — ' + u.full_name : ''}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Máy chủ cần truy cập</label><select class="form-control" id="reqServer">${_servers.map(s => `<option value="${s.id}">${s.name} (${s.protocol.toUpperCase()} :${s.port})</option>`).join('')}</select></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>Thời lượng (phút)</label><input class="form-control" id="reqMinutes" type="number" value="30" min="1" max="480"></div>
                    <div class="form-group"><label>Lý do</label><input class="form-control" id="reqReason" placeholder="VD: Bảo trì hệ thống"></div>
                </div>
                <button class="btn btn-primary" onclick="createRequest()">🔑 Gửi yêu cầu</button>
            </div>
        </div>
        <div class="card">
            <div class="card-header"><h3>📃 Lịch sử Yêu cầu (${_requests.length})</h3></div>
            <div class="card-body table-wrapper">
                <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Thời lượng</th><th>Lý do</th><th>Trạng thái</th><th>Thời gian gửi</th></tr></thead>
                <tbody>${_requests.slice().reverse().map(r => `<tr>
                    <td><strong>${userName(r.user_id)}</strong></td>
                    <td>${serverName(r.server_id)}</td>
                    <td>${r.requested_minutes} phút</td>
                    <td>${r.reason}</td>
                    <td>${statusBadge(r.status)}</td>
                    <td>${fmtDate(r.requested_at)}</td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.createRequest = async function() {
    try {
        await api('POST', '/access/requests/', {
            user_id: document.getElementById('reqUser').value,
            server_id: document.getElementById('reqServer').value,
            requested_minutes: parseInt(document.getElementById('reqMinutes').value),
            reason: document.getElementById('reqReason').value
        });
        toast('Đã gửi yêu cầu truy cập thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Approvals ──────────────────────────
function renderApprovals() {
    const pending = _requests.filter(r => r.status === 'pending');
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h3>✅ Yêu cầu Chờ Phê duyệt (${pending.length})</h3></div>
            <div class="card-body table-wrapper">
                ${pending.length === 0 ? '<div class="empty-state"><div class="empty-icon">🎉</div><p>Không có yêu cầu nào chờ duyệt</p></div>' : `
                <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Thời lượng</th><th>Lý do</th><th>Thời gian gửi</th><th>Hành động</th></tr></thead>
                <tbody>${pending.map(r => `<tr>
                    <td><strong>${userName(r.user_id)}</strong></td>
                    <td>${serverName(r.server_id)}</td>
                    <td>${r.requested_minutes} phút</td>
                    <td>${r.reason}</td>
                    <td>${fmtDate(r.requested_at)}</td>
                    <td>
                        <div class="btn-group">
                            <button class="btn btn-success btn-sm" onclick="reviewRequest('${r.id}', 'approved')">✅ Duyệt</button>
                            <button class="btn btn-danger btn-sm" onclick="reviewRequest('${r.id}', 'rejected')">❌ Từ chối</button>
                        </div>
                    </td>
                </tr>`).join('')}</tbody></table>`}
            </div>
        </div>
    `;
}

window.reviewRequest = async function(id, status) {
    const action = status === 'approved' ? 'DUYỆT' : 'TỪ CHỐI';
    if (!confirm(`Bạn có chắc muốn ${action} yêu cầu này?`)) return;
    try {
        await api('POST', `/access/requests/${id}/review`, { status });
        toast(`Đã ${action.toLowerCase()} yêu cầu thành công!`, status === 'approved' ? 'success' : 'info');
        navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Active Grants ──────────────────────
function renderGrants() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header"><h3>⚡ Quyền Đang Hoạt Động (${_grants.length})</h3></div>
            <div class="card-body table-wrapper">
                ${_grants.length === 0 ? '<div class="empty-state"><div class="empty-icon">🔒</div><p>Không có quyền nào đang hoạt động</p></div>' : `
                <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Cấp quyền lúc</th><th>Hết hạn lúc</th><th>Thời gian còn lại</th><th>Hành động</th></tr></thead>
                <tbody>${_grants.map(g => {
                    const remaining = new Date(g.expires_at) - new Date();
                    const mins = Math.max(0, Math.floor(remaining / 60000));
                    const secs = Math.max(0, Math.floor((remaining % 60000) / 1000));
                    const urgent = mins < 1;
                    return `<tr>
                        <td><strong>${userName(g.user_id)}</strong></td>
                        <td>${serverName(g.server_id)}</td>
                        <td>${fmtDate(g.granted_at)}</td>
                        <td>${fmtDate(g.expires_at)}</td>
                        <td><span class="countdown ${urgent ? 'urgent' : ''}">${mins}m ${secs}s</span></td>
                        <td><button class="btn btn-danger btn-sm" onclick="revokeGrant('${g.id}')">🔴 Thu hồi</button></td>
                    </tr>`;
                }).join('')}</tbody></table>`}
            </div>
        </div>
    `;
    // Auto refresh every 5s
    if (_grants.length > 0) {
        setTimeout(() => { if (location.hash === '#grants') navigate(); }, 5000);
    }
}

window.revokeGrant = async function(id) {
    if (!confirm('Bạn có chắc muốn THU HỒI quyền này ngay lập tức?')) return;
    try {
        await api('POST', `/access/grants/${id}/revoke`);
        toast('Đã thu hồi quyền truy cập thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ── PAGE: Audit Trail ────────────────────────
function renderAudit() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr;gap:16px;">
            <div class="card">
                <div class="card-header"><h3>📹 Nhật ký Phiên làm việc (${_sessions.length})</h3></div>
                <div class="card-body table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Bắt đầu</th><th>Kết thúc</th><th>Trạng thái</th><th>Video</th><th>SHA-256 Hash</th></tr></thead>
                    <tbody>${_sessions.slice().reverse().map(s => `<tr>
                        <td><strong>${userName(s.user_id)}</strong></td>
                        <td>${serverName(s.server_id)}</td>
                        <td>${fmtDate(s.start_time)}</td>
                        <td>${fmtDate(s.end_time)}</td>
                        <td>${statusBadge(s.status)}</td>
                        <td>${s.recording_url ? `<a href="${s.recording_url}" target="_blank" class="btn btn-ghost btn-sm">▶ Xem</a>` : '<span style="color:var(--text-muted)">—</span>'}</td>
                        <td>${s.recording_hash ? `<span class="tag" title="${s.recording_hash}">${s.recording_hash.substring(0, 16)}…</span>` : '<span style="color:var(--text-muted)">—</span>'}</td>
                    </tr>`).join('')}</tbody></table>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><h3>📊 Nhật ký Hệ thống (${_auditLogs.length})</h3></div>
                <div class="card-body table-wrapper">
                    <table><thead><tr><th>Thời gian</th><th>Người dùng</th><th>Hành động</th><th>Đối tượng</th><th>Chi tiết</th></tr></thead>
                    <tbody>${_auditLogs.slice().reverse().map(l => `<tr>
                        <td>${fmtDate(l.timestamp)}</td>
                        <td>${userName(l.user_id)}</td>
                        <td>${badge(l.action, l.action.includes('APPROVED') ? 'approved' : l.action.includes('REVOKE') ? 'rejected' : 'pending')}</td>
                        <td>${l.target_type || '—'}</td>
                        <td>${l.details || '—'}</td>
                    </tr>`).join('')}</tbody></table>
                </div>
            </div>
        </div>
    `;
}
