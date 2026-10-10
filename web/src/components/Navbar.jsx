import React from 'react';

export function Navbar({ authState, onLogout, onOpenLogin, activeTab, onTabChange }) {
  const { loggedIn, passwordProtectionEnabled } = authState;

  return (
    <header className="navbar">
      <div className="navbar-content">
        <div className="brand">
          <div className="brand-icon">⚡</div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">Y2A-Auto</span>
              <span className="brand-tag">v2.0 REST</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
              YouTube 自动化发布至 AcFun & Bilibili
            </div>
          </div>
        </div>

        {/* 顶部主选项卡切换导航 */}
        <div style={{
          display: 'flex',
          background: 'rgba(255, 255, 255, 0.05)',
          padding: '3px',
          borderRadius: '10px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <button
            type="button"
            onClick={() => onTabChange && onTabChange('tasks')}
            style={{
              padding: '6px 16px',
              fontSize: '0.85rem',
              fontWeight: activeTab === 'tasks' ? 600 : 400,
              background: activeTab === 'tasks' ? 'var(--primary-color, #38bdf8)' : 'transparent',
              color: activeTab === 'tasks' ? '#0f172a' : 'var(--text-dim)',
              border: 'none',
              borderRadius: '7px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            <span>📺</span>
            <span>单任务视频</span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange && onTabChange('playlist')}
            style={{
              padding: '6px 16px',
              fontSize: '0.85rem',
              fontWeight: activeTab === 'playlist' ? 600 : 400,
              background: activeTab === 'playlist' ? 'var(--primary-color, #38bdf8)' : 'transparent',
              color: activeTab === 'playlist' ? '#0f172a' : 'var(--text-dim)',
              border: 'none',
              borderRadius: '7px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            <span>📑</span>
            <span>Playlist 监控</span>
          </button>
        </div>

        <div className="nav-actions">
          <div className="status-badge">
            <span className={`status-dot ${loggedIn ? 'online' : 'offline'}`} />
            <span>
              {!passwordProtectionEnabled
                ? '免密模式'
                : loggedIn
                ? '已认证'
                : '未登录'}
            </span>
          </div>

          {passwordProtectionEnabled && (
            loggedIn ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onLogout}
                style={{ padding: '7px 14px', fontSize: '0.825rem' }}
              >
                退出登录
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onOpenLogin}
                style={{ padding: '7px 16px', fontSize: '0.825rem' }}
              >
                登录系统
              </button>
            )
          )}
        </div>
      </div>
    </header>
  );
}

