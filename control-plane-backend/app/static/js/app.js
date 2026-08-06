/* ============================================
   PAM GATEWAY v2.0 — ADMIN CONTROL PLANE SPA
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
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

function shortId(uuid) { return uuid ? uuid.substring(0, 8) + '…' : '—'; }

function fmtDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function badge(text, type) { return `<span class="badge badge-${type}">${text}</span>`; }

function statusBadge(s) {
    const m = { pending: 'pending', approved: 'approved', rejected: 'rejected', expired: 'expired', active: 'active', completed: 'approved', revoked: 'rejected' };
    const labels = { pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Từ chối', expired: 'Hết hạn', active: 'Đang hoạt động', completed: 'Hoàn thành', revoked: 'Đã thu hồi' };
    return badge(labels[s] || s, m[s] || 'expired');
}

function protocolBadge(p) { return badge(p.toUpperCase(), p); }

function groupBadge(name) {
    if (!name) return badge('—', 'expired');
    if (name.includes('Admin')) return badge(name, 'admin');
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
        updatePendingBadge();
    } catch (e) { console.error('Load error:', e); }
}

function updatePendingBadge() {
    const pendingCount = _requests.filter(r => r.status === 'pending').length;
    const badge = document.getElementById('pendingBadge');
    if (badge) {
        if (pendingCount > 0) {
            badge.textContent = pendingCount;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    }
}

function userName(id) { const u = _users.find(u => u.id === id); return u ? u.username : shortId(id); }
function serverName(id) { const s = _servers.find(s => s.id === id); return s ? s.name : shortId(id); }
function groupName(id) { const g = _groups.find(g => g.id === id); return g ? g.name : shortId(id); }

// ── Router ───────────────────────────────────
const pages = {
    dashboard:  { title: 'Dashboard',               render: renderDashboard  },
    users:      { title: 'Quản lý Người dùng',       render: renderUsers      },
    groups:     { title: 'Quản lý Nhóm',             render: renderGroups     },
    servers:    { title: 'Quản lý Máy chủ',          render: renderServers    },
    policies:   { title: 'Chính sách Phân quyền',    render: renderPolicies   },
    approvals:  { title: 'Phê Duyệt Yêu Cầu',       render: renderApprovals  },
    grants:     { title: 'Quyền Đang Hoạt Động',     render: renderGrants     },
    audit:      { title: 'Audit Trail',              render: renderAudit      },
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
document.getElementById('menuToggle').onclick = () => document.getElementById('sidebar').classList.toggle('open');

// ═══════════════════════════════════════════════════
// PAGE: Dashboard
// ═══════════════════════════════════════════════════
function renderDashboard() {
    const pending = _requests.filter(r => r.status === 'pending').length;
    const el = document.getElementById('contentArea');

    const recentRequests = _requests.slice().reverse().slice(0, 6);
    const recentAudit = _auditLogs.slice(0, 5);

    el.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-icon">👤</div><div class="stat-value" style="color:var(--accent-blue)">${_users.length}</div><div class="stat-label">Người dùng</div></div>
            <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-value" style="color:var(--accent-purple)">${_groups.length}</div><div class="stat-label">Nhóm</div></div>
            <div class="stat-card"><div class="stat-icon">🖥️</div><div class="stat-value" style="color:var(--accent-cyan)">${_servers.length}</div><div class="stat-label">Máy chủ</div></div>
            <div class="stat-card"><div class="stat-icon">🔐</div><div class="stat-value" style="color:var(--accent-orange)">${_policies.length}</div><div class="stat-label">Chính sách</div></div>
            <div class="stat-card" style="${pending > 0 ? 'border-color:var(--accent-yellow);' : ''}">
                <div class="stat-icon">⏳</div>
                <div class="stat-value" style="color:var(--accent-yellow)">${pending}</div>
                <div class="stat-label">Chờ duyệt</div>
                ${pending > 0 ? `<a href="#approvals" onclick="navigate()" style="display:block;margin-top:8px;font-size:12px;color:var(--accent-yellow);text-decoration:none;">→ Xem ngay</a>` : ''}
            </div>
            <div class="stat-card"><div class="stat-icon">⚡</div><div class="stat-value" style="color:var(--accent-green)">${_grants.length}</div><div class="stat-label">Quyền đang hoạt động</div></div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
            <div class="card">
                <div class="card-header">
                    <h3>📋 Yêu cầu gần đây</h3>
                    <a href="#approvals" class="btn btn-ghost btn-sm" style="text-decoration:none;">Xem tất cả →</a>
                </div>
                <div class="table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Trạng thái</th><th>Thời gian</th></tr></thead>
                    <tbody>${recentRequests.map(r => `<tr>
                        <td><strong>${userName(r.user_id)}</strong></td>
                        <td>${serverName(r.server_id)}</td>
                        <td>${statusBadge(r.status)}</td>
                        <td style="font-size:11px;color:var(--text-muted)">${fmtDate(r.requested_at)}</td>
                    </tr>`).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px">Chưa có yêu cầu</td></tr>'}</tbody></table>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <h3>⚡ Quyền đang hoạt động</h3>
                </div>
                <div class="table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Hết hạn</th></tr></thead>
                    <tbody>${_grants.map(g => `<tr>
                        <td><strong>${userName(g.user_id)}</strong></td>
                        <td>${serverName(g.server_id)}</td>
                        <td style="font-size:11px;color:var(--accent-yellow)">${fmtDate(g.expires_at)}</td>
                    </tr>`).join('') || '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:20px">Không có quyền đang hoạt động</td></tr>'}</tbody></table>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>📊 Nhật ký hệ thống gần đây</h3>
                <a href="#audit" class="btn btn-ghost btn-sm" style="text-decoration:none;">Xem đầy đủ →</a>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Thời gian</th><th>Người dùng</th><th>Hành động</th><th>Chi tiết</th></tr></thead>
                <tbody>${recentAudit.map(l => `<tr>
                    <td style="font-size:11px;color:var(--text-muted);white-space:nowrap">${fmtDate(l.timestamp)}</td>
                    <td>${userName(l.user_id)}</td>
                    <td>${badge(l.action, l.action.includes('APPROVED') ? 'approved' : l.action.includes('REVOKED') || l.action.includes('REJECTED') ? 'rejected' : 'pending')}</td>
                    <td style="font-size:12px;color:var(--text-secondary)">${l.details || '—'}</td>
                </tr>`).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px">Chưa có log</td></tr>'}</tbody></table>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════
// PAGE: Users
// ═══════════════════════════════════════════════════
function renderUsers() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>👤 Danh sách Người dùng (${_users.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateUserForm()">+ Thêm User</button>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Username</th><th>Email</th><th>Họ tên</th><th>Nhóm thành viên</th><th>Trạng thái</th><th>Hành động</th></tr></thead>
                <tbody>${_users.map(u => {
                    const userGroups = _groups.filter(g => g.users && g.users.some(gu => gu.id === u.id));
                    return `<tr>
                        <td><strong>${u.username}</strong></td>
                        <td style="color:var(--text-secondary)">${u.email || '—'}</td>
                        <td>${u.full_name || '—'}</td>
                        <td>
                            <div class="member-list">
                                ${userGroups.length > 0
                                    ? userGroups.map(g => `<span class="member-chip">${g.name}<button onclick="removeFromGroup('${u.id}','${g.id}','${u.username}','${g.name}')" title="Xóa khỏi nhóm">×</button></span>`).join('')
                                    : '<span style="color:var(--text-muted);font-size:12px">Chưa gán nhóm</span>'
                                }
                            </div>
                        </td>
                        <td>${u.is_active ? badge('Active', 'active') : badge('Inactive', 'expired')}</td>
                        <td><button class="btn btn-ghost btn-sm" onclick="showAssignGroupModal('${u.id}', '${u.username}')">+ Gán nhóm</button></td>
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
    const username = document.getElementById('newUsername').value.trim();
    if (!username) { toast('Vui lòng nhập username', 'error'); return; }
    try {
        await api('POST', '/auth/users/', {
            username,
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

window.removeFromGroup = async function(userId, groupId, username, groupName) {
    if (!confirm(`Xóa "${username}" khỏi nhóm "${groupName}"?`)) return;
    try {
        await api('DELETE', `/auth/users/${userId}/groups/${groupId}`);
        toast(`Đã xóa ${username} khỏi ${groupName}`, 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Groups
// ═══════════════════════════════════════════════════
function renderGroups() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>👥 Danh sách Nhóm (${_groups.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateGroupForm()">+ Tạo nhóm</button>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Tên nhóm</th><th>Mô tả</th><th>Thành viên</th><th>Server được phép</th><th>Hành động</th></tr></thead>
                <tbody>${_groups.map(g => {
                    const members = g.users || [];
                    const gPolicies = _policies.filter(p => p.group_id === g.id);
                    return `<tr>
                        <td>${groupBadge(g.name)}</td>
                        <td style="color:var(--text-secondary)">${g.description || '—'}</td>
                        <td>
                            <div class="member-list">
                                ${members.length > 0
                                    ? members.map(m => `<span class="member-chip">👤 ${m.username}</span>`).join('')
                                    : '<span style="color:var(--text-muted);font-size:12px">Chưa có thành viên</span>'
                                }
                            </div>
                        </td>
                        <td>${gPolicies.length > 0
                            ? gPolicies.map(p => `<span class="tag">${serverName(p.server_id)} <span style="color:var(--accent-yellow)">${p.max_duration_minutes}p</span></span>`).join('')
                            : '<span style="color:var(--text-muted);font-size:12px">Chưa gán policy</span>'
                        }</td>
                        <td><button class="btn btn-danger btn-sm" onclick="deleteGroup('${g.id}','${g.name}')">Xóa</button></td>
                    </tr>`;
                }).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.showCreateGroupForm = function() {
    showModal('Tạo Nhóm mới', `
        <div class="form-group"><label>Tên nhóm</label><input class="form-control" id="newGroupName" placeholder="VD: PAM-DevOps"></div>
        <div class="form-group"><label>Mô tả</label><input class="form-control" id="newGroupDesc" placeholder="Mô tả ngắn về nhóm này"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="createGroup()">Tạo nhóm</button>`);
};

window.createGroup = async function() {
    const name = document.getElementById('newGroupName').value.trim();
    if (!name) { toast('Vui lòng nhập tên nhóm', 'error'); return; }
    try {
        await api('POST', '/auth/groups/', { name, description: document.getElementById('newGroupDesc').value || null });
        hideModal(); toast('Đã tạo Nhóm thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.deleteGroup = async function(id, name) {
    if (!confirm(`Bạn có chắc muốn xóa nhóm "${name}"? Thao tác này không thể hoàn tác.`)) return;
    try {
        await api('DELETE', `/auth/groups/${id}`);
        toast(`Đã xóa nhóm "${name}".`, 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Servers
// ═══════════════════════════════════════════════════
function renderServers() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>🖥️ Danh sách Máy chủ (${_servers.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showCreateServerForm()">+ Thêm Server</button>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Tên</th><th>Giao thức</th><th>Địa chỉ IP</th><th>Cổng</th><th>Guac Connection ID</th><th>Tags</th><th>Hành động</th></tr></thead>
                <tbody>${_servers.map(s => `<tr>
                    <td><strong>${s.name}</strong></td>
                    <td>${protocolBadge(s.protocol)}</td>
                    <td style="font-family:monospace;font-size:12px">${s.ip || s.host}</td>
                    <td style="font-family:monospace;font-size:12px">${s.port}</td>
                    <td><span class="tag">#${s.guacamole_connection_id}</span></td>
                    <td>${s.tags && s.tags.length ? s.tags.map(t => `<span class="tag">${t}</span>`).join('') : '<span style="color:var(--text-muted)">—</span>'}</td>
                    <td>
                        <div class="btn-group">
                            <button class="btn btn-ghost btn-sm" onclick="showEditServerForm('${s.id}','${s.name}')">✏️ Sửa</button>
                            <button class="btn btn-danger btn-sm" onclick="deleteServer('${s.id}','${s.name}')">🗑️ Xóa</button>
                        </div>
                    </td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.showCreateServerForm = function() {
    showModal('Thêm Máy chủ mới', `
        <div class="form-group"><label>Tên hiển thị</label><input class="form-control" id="srvName" placeholder="VD: Linux Production Server"></div>
        <div class="form-row">
            <div class="form-group"><label>Giao thức</label><select class="form-control" id="srvProtocol"><option value="ssh">SSH</option><option value="vnc">VNC</option><option value="rdp">RDP</option></select></div>
            <div class="form-group"><label>Cổng</label><input class="form-control" id="srvPort" type="number" value="22"></div>
        </div>
        <div class="form-group"><label>Địa chỉ IP / Host</label><input class="form-control" id="srvHost" placeholder="VD: 192.168.1.100"></div>
        <div class="form-group"><label>Guacamole Connection ID</label><input class="form-control" id="srvConnId" placeholder="VD: 1"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="createServer()">Thêm Server</button>`);
    document.getElementById('srvProtocol').onchange = function() {
        const portMap = { ssh: 22, vnc: 5900, rdp: 3389 };
        document.getElementById('srvPort').value = portMap[this.value] || 22;
    };
};

window.createServer = async function() {
    const name = document.getElementById('srvName').value.trim();
    const host = document.getElementById('srvHost').value.trim();
    if (!name || !host) { toast('Vui lòng điền đủ thông tin', 'error'); return; }
    try {
        await api('POST', '/servers/', {
            name,
            ip: host,
            port: parseInt(document.getElementById('srvPort').value),
            protocol: document.getElementById('srvProtocol').value,
            guacamole_connection_id: document.getElementById('srvConnId').value
        });
        hideModal(); toast('Đã thêm Server thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.showEditServerForm = function(id, currentName) {
    const s = _servers.find(s => s.id === id);
    if (!s) return;
    showModal(`Chỉnh sửa Server "${currentName}"`, `
        <div class="form-group"><label>Tên hiển thị</label><input class="form-control" id="editSrvName" value="${s.name}"></div>
        <div class="form-row">
            <div class="form-group"><label>Giao thức</label>
                <select class="form-control" id="editSrvProtocol">
                    ${['ssh','vnc','rdp'].map(p => `<option value="${p}" ${s.protocol === p ? 'selected' : ''}>${p.toUpperCase()}</option>`).join('')}
                </select>
            </div>
            <div class="form-group"><label>Cổng</label><input class="form-control" id="editSrvPort" type="number" value="${s.port}"></div>
        </div>
        <div class="form-group"><label>Địa chỉ IP</label><input class="form-control" id="editSrvHost" value="${s.ip || s.host}"></div>
        <div class="form-group"><label>Guacamole Connection ID</label><input class="form-control" id="editSrvConnId" value="${s.guacamole_connection_id}"></div>
    `, `<button class="btn btn-ghost" onclick="hideModal()">Hủy</button><button class="btn btn-primary" onclick="updateServer('${id}')">Lưu thay đổi</button>`);
};

window.updateServer = async function(id) {
    try {
        await api('PATCH', `/servers/${id}`, {
            name: document.getElementById('editSrvName').value,
            ip: document.getElementById('editSrvHost').value,
            port: parseInt(document.getElementById('editSrvPort').value),
            protocol: document.getElementById('editSrvProtocol').value,
            guacamole_connection_id: document.getElementById('editSrvConnId').value
        });
        hideModal(); toast('Đã cập nhật Server!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.deleteServer = async function(id, name) {
    if (!confirm(`Bạn có chắc muốn xóa Server "${name}"?\nTất cả policy liên quan cũng sẽ bị ảnh hưởng.`)) return;
    try {
        await api('DELETE', `/servers/${id}`);
        toast(`Đã xóa Server "${name}".`, 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Policies
// ═══════════════════════════════════════════════════
const POLICY_TEMPLATES = [
    { icon: '🔍', name: 'Read-Only SSH', desc: 'SSH 30 phút, cần duyệt', minutes: 30, approval: true, protocol: 'ssh' },
    { icon: '💼', name: 'Standard SSH', desc: 'SSH 60 phút, cần duyệt', minutes: 60, approval: true, protocol: 'ssh' },
    { icon: '🖥️', name: 'Standard RDP', desc: 'RDP 60 phút, cần duyệt', minutes: 60, approval: true, protocol: 'rdp' },
    { icon: '👁️', name: 'VNC View', desc: 'VNC 60 phút, cần duyệt', minutes: 60, approval: true, protocol: 'vnc' },
    { icon: '🚀', name: 'Deploy Access', desc: 'SSH 120 phút, cần duyệt', minutes: 120, approval: true, protocol: 'ssh' },
    { icon: '🔧', name: 'Maintenance', desc: 'SSH/RDP 240 phút, cần duyệt', minutes: 240, approval: true, protocol: 'ssh' },
    { icon: '🚨', name: 'Emergency', desc: 'SSH 480 phút, ưu tiên cao', minutes: 480, approval: true, protocol: 'ssh' },
    { icon: '⚡', name: 'Quick Access', desc: 'SSH 15 phút, tự động cấp', minutes: 15, approval: false, protocol: 'ssh' },
    { icon: '🔄', name: 'CI/CD Pipeline', desc: 'SSH 30 phút, tự động cấp', minutes: 30, approval: false, protocol: 'ssh' },
    { icon: '📊', name: 'Audit Session', desc: 'RDP 180 phút, cần duyệt', minutes: 180, approval: true, protocol: 'rdp' },
    { icon: '🗄️', name: 'DB Admin', desc: 'SSH 90 phút, cần duyệt', minutes: 90, approval: true, protocol: 'ssh' },
    { icon: '🌐', name: 'Web Server', desc: 'SSH 60 phút, tự động cấp', minutes: 60, approval: false, protocol: 'ssh' },
];

function renderPolicies() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card" style="margin-bottom:16px;">
            <div class="card-header"><h3>📦 Policy Templates — Chọn nhanh</h3><span style="font-size:12px;color:var(--text-muted)">Bấm vào template để điền tự động vào form bên dưới</span></div>
            <div class="card-body">
                <div class="template-grid">
                    ${POLICY_TEMPLATES.map((t, i) => `
                        <div class="template-card" onclick="applyTemplate(${i})">
                            <div class="t-icon">${t.icon}</div>
                            <div class="t-name">${t.name}</div>
                            <div class="t-desc">${t.desc}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom:16px;">
            <div class="card-header"><h3>🔐 Tạo Chính sách mới</h3></div>
            <div class="card-body">
                <div class="form-row">
                    <div class="form-group"><label>Nhóm</label>
                        <select class="form-control" id="polGroup">
                            ${_groups.map(g => `<option value="${g.id}">${g.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group"><label>Máy chủ</label>
                        <select class="form-control" id="polServer">
                            ${_servers.map(s => `<option value="${s.id}">${s.name} (${s.protocol.toUpperCase()})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group"><label>Thời lượng tối đa (phút)</label>
                        <input class="form-control" id="polMaxMin" type="number" value="60" min="1" max="480">
                    </div>
                    <div class="form-group"><label>Yêu cầu phê duyệt</label>
                        <select class="form-control" id="polApproval">
                            <option value="true">✅ Bắt buộc Admin duyệt</option>
                            <option value="false">⚡ Tự động cấp ngay</option>
                        </select>
                    </div>
                </div>
                <button class="btn btn-primary" onclick="createPolicy()">+ Tạo chính sách</button>
            </div>
        </div>

        <div class="card">
            <div class="card-header"><h3>📋 Danh sách Chính sách (${_policies.length})</h3></div>
            <div class="table-wrapper">
                <table><thead><tr><th>Nhóm</th><th>Máy chủ</th><th>Thời lượng tối đa</th><th>Phê duyệt</th><th>Ngày tạo</th><th>Hành động</th></tr></thead>
                <tbody>${_policies.map(p => `<tr>
                    <td>${groupBadge(groupName(p.group_id))}</td>
                    <td><strong>${serverName(p.server_id)}</strong></td>
                    <td><span style="color:var(--accent-yellow);font-weight:600">${p.max_duration_minutes} phút</span></td>
                    <td>${p.require_approval ? badge('Bắt buộc duyệt', 'pending') : badge('Tự động cấp', 'active')}</td>
                    <td style="font-size:11px;color:var(--text-muted)">${fmtDate(p.created_at)}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deletePolicy('${p.id}')">🗑️ Xóa</button></td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.applyTemplate = function(index) {
    const t = POLICY_TEMPLATES[index];
    const minEl = document.getElementById('polMaxMin');
    const approvalEl = document.getElementById('polApproval');
    if (minEl) minEl.value = t.minutes;
    if (approvalEl) approvalEl.value = t.approval ? 'true' : 'false';
    toast(`Đã áp dụng template "${t.name}"`, 'info');
    document.getElementById('polGroup')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
};

window.createPolicy = async function() {
    const groupEl = document.getElementById('polGroup');
    const serverEl = document.getElementById('polServer');
    if (!groupEl || !serverEl) return;
    try {
        await api('POST', '/policy/group-server/', {
            group_id: groupEl.value,
            server_id: serverEl.value,
            max_duration_minutes: parseInt(document.getElementById('polMaxMin').value),
            require_approval: document.getElementById('polApproval').value === 'true'
        });
        toast('Đã tạo chính sách thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

window.deletePolicy = async function(id) {
    if (!confirm('Xóa chính sách này?')) return;
    try { await api('DELETE', `/policy/group-server/${id}`); toast('Đã xóa chính sách.', 'success'); navigate(); }
    catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Approvals
// ═══════════════════════════════════════════════════
function renderApprovals() {
    const pending = _requests.filter(r => r.status === 'pending');
    const history = _requests.filter(r => r.status !== 'pending').slice().reverse().slice(0, 20);
    const el = document.getElementById('contentArea');

    el.innerHTML = `
        <div style="margin-bottom:20px;">
            <h3 style="font-size:16px;font-weight:700;margin-bottom:4px;">
                ${pending.length > 0
                    ? `<span style="color:var(--accent-yellow)">⚠️ ${pending.length} yêu cầu đang chờ phê duyệt</span>`
                    : `<span style="color:var(--accent-green)">✅ Không có yêu cầu nào chờ duyệt</span>`
                }
            </h3>
            <p style="font-size:13px;color:var(--text-muted)">Xem xét và phê duyệt hoặc từ chối yêu cầu truy cập của người dùng.</p>
        </div>

        ${pending.length === 0
            ? `<div class="card"><div class="card-body"><div class="empty-state"><div class="empty-icon">🎉</div><p>Tất cả yêu cầu đã được xử lý</p></div></div></div>`
            : pending.map(r => {
                const user = _users.find(u => u.id === r.user_id);
                const server = _servers.find(s => s.id === r.server_id);
                return `
                <div class="approval-card">
                    <div class="ac-avatar">👤</div>
                    <div class="ac-info">
                        <div class="ac-title">
                            <strong>${user ? user.username : shortId(r.user_id)}</strong>
                            ${user?.full_name ? `<span style="color:var(--text-muted);font-weight:400"> — ${user.full_name}</span>` : ''}
                            <span style="margin:0 8px;color:var(--text-muted)">→</span>
                            🖥️ <strong>${server ? server.name : shortId(r.server_id)}</strong>
                            ${server ? protocolBadge(server.protocol) : ''}
                        </div>
                        <div class="ac-meta">
                            ⏱️ <strong style="color:var(--accent-yellow)">${r.requested_minutes} phút</strong> &nbsp;·&nbsp;
                            📅 Gửi lúc ${fmtDate(r.requested_at)}
                        </div>
                        <div class="ac-reason">"${r.reason}"</div>
                    </div>
                    <div class="ac-actions">
                        <button class="btn btn-success" onclick="reviewRequest('${r.id}', 'approved')">✅ Duyệt</button>
                        <button class="btn btn-danger" onclick="reviewRequest('${r.id}', 'rejected')">❌ Từ chối</button>
                    </div>
                </div>`;
            }).join('')
        }

        <div class="card" style="margin-top:24px;">
            <div class="card-header"><h3>📜 Lịch sử phê duyệt (${history.length} gần nhất)</h3></div>
            <div class="table-wrapper">
                <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Thời lượng</th><th>Lý do</th><th>Trạng thái</th><th>Thời gian gửi</th></tr></thead>
                <tbody>${history.map(r => `<tr>
                    <td><strong>${userName(r.user_id)}</strong></td>
                    <td>${serverName(r.server_id)}</td>
                    <td>${r.requested_minutes} phút</td>
                    <td style="color:var(--text-muted);font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis">${r.reason}</td>
                    <td>${statusBadge(r.status)}</td>
                    <td style="font-size:11px;color:var(--text-muted)">${fmtDate(r.requested_at)}</td>
                </tr>`).join('')}</tbody></table>
            </div>
        </div>
    `;
}

window.reviewRequest = async function(id, status) {
    const action = status === 'approved' ? 'DUYỆT' : 'TỪ CHỐI';
    if (!confirm(`Bạn có chắc muốn ${action} yêu cầu này?`)) return;
    try {
        await api('POST', `/access/requests/${id}/review`, { status });
        toast(`Đã ${action === 'DUYỆT' ? 'duyệt' : 'từ chối'} yêu cầu thành công!`, status === 'approved' ? 'success' : 'info');
        navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Active Grants
// ═══════════════════════════════════════════════════
function renderGrants() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>⚡ Quyền Đang Hoạt Động (${_grants.length})</h3>
                <span style="font-size:12px;color:var(--text-muted)">Tự động cập nhật mỗi giây</span>
            </div>
            ${_grants.length === 0
                ? `<div class="card-body"><div class="empty-state"><div class="empty-icon">🔒</div><p>Không có quyền nào đang hoạt động</p></div></div>`
                : `<div class="table-wrapper">
                    <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Giao thức</th><th>Cấp lúc</th><th>Hết hạn lúc</th><th>Thời gian còn lại</th><th>Hành động</th></tr></thead>
                    <tbody>${_grants.map(g => {
                        const server = _servers.find(s => s.id === g.server_id);
                        const remainMs = Math.max(0, new Date(g.expires_at).getTime() - Date.now());
                        const totalSecs = Math.floor(remainMs / 1000);
                        const mins = Math.floor(totalSecs / 60);
                        const secs = totalSecs % 60;
                        const urgent = mins < 5;
                        return `<tr>
                            <td><strong>${userName(g.user_id)}</strong></td>
                            <td>${serverName(g.server_id)}</td>
                            <td>${server ? protocolBadge(server.protocol) : '—'}</td>
                            <td style="font-size:11px;color:var(--text-muted)">${fmtDate(g.granted_at)}</td>
                            <td style="font-size:11px;color:var(--text-muted)">${fmtDate(g.expires_at)}</td>
                            <td><span class="countdown ${urgent ? 'urgent' : ''}" data-expires="${g.expires_at}">${mins}m ${secs < 10 ? '0' : ''}${secs}s</span></td>
                            <td><button class="btn btn-danger btn-sm" onclick="revokeGrant('${g.id}')">🔴 Thu hồi</button></td>
                        </tr>`;
                    }).join('')}</tbody></table>
                </div>`
            }
        </div>
    `;

    if (_grants.length > 0) {
        startCountdownTimers();
    }
}

function startCountdownTimers() {
    const interval = setInterval(() => {
        const countdowns = document.querySelectorAll('.countdown[data-expires]');
        if (countdowns.length === 0) { clearInterval(interval); return; }
        countdowns.forEach(el => {
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

window.revokeGrant = async function(id) {
    if (!confirm('Bạn có chắc muốn THU HỒI quyền này ngay lập tức?')) return;
    try {
        await api('POST', `/access/grants/${id}/revoke`);
        toast('Đã thu hồi quyền truy cập thành công!', 'success'); navigate();
    } catch (e) { toast(e.message, 'error'); }
};

// ═══════════════════════════════════════════════════
// PAGE: Audit Trail
// ═══════════════════════════════════════════════════
function renderAudit() {
    const el = document.getElementById('contentArea');
    el.innerHTML = `
        <div class="card" style="margin-bottom:16px;">
            <div class="card-header">
                <h3>📹 Nhật ký Phiên làm việc — Session Log (${_sessions.length})</h3>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Người dùng</th><th>Máy chủ</th><th>Thời gian truy cập</th><th>Thời lượng</th><th>Trạng thái</th><th>Ghi hình</th></tr></thead>
                <tbody>${_sessions.slice().reverse().map(s => {
                    const startTime = s.start_time ? new Date(s.start_time) : null;
                    const endTime = s.end_time ? new Date(s.end_time) : null;
                    const durationMs = startTime && endTime ? endTime - startTime : null;
                    const durationMins = durationMs ? Math.round(durationMs / 60000) : null;
                    return `<tr>
                        <td><strong>${userName(s.user_id)}</strong></td>
                        <td>${serverName(s.server_id)}</td>
                        <td>
                            <div class="session-timeline">
                                <span class="tl-from">▶ ${startTime ? startTime.toLocaleString('vi-VN', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '—'}</span>
                                <span class="tl-arrow">→</span>
                                <span class="tl-to">■ ${endTime ? endTime.toLocaleString('vi-VN', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '<em style="color:var(--accent-green)">Đang hoạt động</em>'}</span>
                            </div>
                        </td>
                        <td>${durationMins != null ? `<span style="color:var(--accent-cyan);font-weight:600">${durationMins} phút</span>` : '<span style="color:var(--accent-green)">Đang chạy</span>'}</td>
                        <td>${statusBadge(s.status)}</td>
                        <td>${s.recording_url
                            ? `<a href="${s.recording_url}" target="_blank" class="btn btn-ghost btn-sm">▶ Xem video</a>`
                            : `<span style="color:var(--text-muted);font-size:12px">${s.recording_file || '—'}</span>`
                        }</td>
                    </tr>`;
                }).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:30px">Chưa có phiên làm việc</td></tr>'}</tbody></table>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>📊 Nhật ký Thao tác Hệ thống — Audit Log (${_auditLogs.length})</h3>
            </div>
            <div class="table-wrapper">
                <table><thead><tr><th>Thời gian</th><th>Người dùng</th><th>Hành động</th><th>Đối tượng</th><th>Chi tiết</th></tr></thead>
                <tbody>${_auditLogs.slice().reverse().map(l => `<tr>
                    <td style="font-size:11px;color:var(--text-muted);white-space:nowrap">${fmtDate(l.timestamp)}</td>
                    <td><strong>${userName(l.user_id)}</strong></td>
                    <td>${badge(l.action,
                        l.action.includes('APPROVED') ? 'approved' :
                        l.action.includes('REVOKED') || l.action.includes('REJECTED') ? 'rejected' :
                        l.action.includes('REQUESTED') ? 'pending' : 'support'
                    )}</td>
                    <td style="color:var(--text-secondary)">${l.target_type || '—'}</td>
                    <td style="font-size:12px;color:var(--text-secondary);max-width:300px">${l.details || '—'}</td>
                </tr>`).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:30px">Chưa có log</td></tr>'}</tbody></table>
            </div>
        </div>
    `;
}
