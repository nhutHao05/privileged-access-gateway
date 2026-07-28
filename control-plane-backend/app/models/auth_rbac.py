import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Table, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

# Bảng phụ để map mối quan hệ Nhiều-Nhiều giữa Users và Groups
user_groups = Table(
    'user_groups', Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('group_id', UUID(as_uuid=True), ForeignKey('groups.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_sub = Column(UUID(as_uuid=True), unique=True, nullable=True)
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    groups = relationship("Group", secondary=user_groups, back_populates="users")

class Group(Base):
    __tablename__ = 'groups'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_group_id = Column(UUID(as_uuid=True), unique=True, nullable=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    users = relationship("User", secondary=user_groups, back_populates="groups")

class Server(Base):
    __tablename__ = 'servers'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String, nullable=False) # rdp | ssh | vnc
    guacamole_connection_id = Column(String, nullable=False)
    tags = Column(ARRAY(String), nullable=True)

class GroupServerPolicy(Base):
    __tablename__ = 'group_server_policy'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey('groups.id'), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey('servers.id'), nullable=False)
    max_duration_minutes = Column(Integer, default=60, nullable=False)
    require_approval = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AccessRequest(Base):
    __tablename__ = 'access_requests'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey('servers.id'), nullable=False)
    reason = Column(String, nullable=False)
    requested_minutes = Column(Integer, nullable=False)
    status = Column(String, default='pending') # pending, approved, rejected, expired, cancelled
    requested_at = Column(DateTime, default=datetime.utcnow)
    decided_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(String, nullable=True)

class ActiveGrant(Base):
    __tablename__ = 'active_grants'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey('access_requests.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey('servers.id'), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False) # Scheduler sẽ quét trường này để tự thu hồi
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(UUID(as_uuid=True), nullable=True)
    revoke_reason = Column(String, nullable=True)

class SessionLog(Base):
    __tablename__ = 'session_logs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey('access_requests.id'), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey('servers.id'), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default='active') # active, completed, revoked
    recording_file = Column(String, nullable=True) # Tên file mp4
    recording_url = Column(String, nullable=True) # Link xem MinIO
    recording_hash = Column(String, nullable=True) # SHA-256 hash chống sửa đổi log

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    action = Column(String, nullable=False) # ACCESS_REQUESTED, ACCESS_APPROVED, ACCESS_REJECTED, ACCESS_REVOKED
    target_type = Column(String, nullable=True) # SERVER, POLICY, USER
    target_id = Column(String, nullable=True)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)