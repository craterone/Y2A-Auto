import React from 'react';

export function Navbar({ authState, onLogout, onOpenLogin }) {
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
