import React, { useState } from 'react';

export function LoginForm({ onLoginSuccess, isModal = false, onClose }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [lockedInfo, setLockedInfo] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) {
      setErrorMsg('请输入访问密码');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    try {
      await onLoginSuccess(password);
      setPassword('');
      if (onClose) onClose();
    } catch (err) {
      if (err.data?.locked) {
        setLockedInfo({
          seconds: err.data.remaining_seconds || 900,
          message: err.data.message || '账户已被临时锁定',
        });
      }
      setErrorMsg(err.message || '登录失败，请检查密码');
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <div className="glass-card" style={{ maxWidth: '440px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px', textAlign: 'center' }}>
        <div style={{
          width: '52px',
          height: '52px',
          background: 'var(--primary-light)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          borderRadius: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '24px',
          margin: '0 auto 16px',
        }}>
          🔐
        </div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: '700', marginBottom: '6px' }}>系统身份验证</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
          当前系统已开启访问密码保护，请验证身份以调用各项自动化功能
        </p>
      </div>

      {errorMsg && (
        <div style={{
          background: 'var(--danger-bg)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          color: '#fca5a5',
          fontSize: '0.85rem',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span>⚠️</span>
          <span>{errorMsg}</span>
        </div>
      )}

      {lockedInfo && (
        <div style={{
          background: 'var(--warning-bg)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          color: '#fcd34d',
          fontSize: '0.85rem',
          marginBottom: '20px',
        }}>
          🔒 <strong>临时锁定保护</strong>: {lockedInfo.message}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="login-password">访问密码</label>
          <div style={{ position: 'relative' }}>
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              className="input-field"
              placeholder="请输入系统密码..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              autoFocus
              style={{ paddingRight: '48px' }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              style={{
                position: 'absolute',
                right: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: 'var(--text-dim)',
                cursor: 'pointer',
                fontSize: '1rem',
                padding: '4px',
              }}
              title={showPassword ? '隐藏密码' : '显示密码'}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
          </div>
          <div className="form-hint">调用 RESTful API /api/login 进行安全校验与会话绑定</div>
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '28px' }}>
          {isModal && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ flex: 1 }}
              onClick={onClose}
              disabled={loading}
            >
              取消
            </button>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            style={{ flex: 2 }}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner" />
                正在验证...
              </>
            ) : (
              '立即登录'
            )}
          </button>
        </div>
      </form>
    </div>
  );

  if (isModal) {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(5, 8, 15, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}>
        {content}
      </div>
    );
  }

  return content;
}
