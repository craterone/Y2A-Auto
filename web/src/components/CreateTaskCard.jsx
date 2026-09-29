import React, { useState } from 'react';

export function CreateTaskCard({ onTaskCreated, isSubmitting, setIsSubmitting }) {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [uploadTarget, setUploadTarget] = useState('acfun');
  const [autoStart, setAutoStart] = useState(true);
  const [lastResult, setLastResult] = useState(null);

  const isPlaylist = youtubeUrl.includes('playlist') || youtubeUrl.includes('list=');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) return;

    setIsSubmitting(true);
    setLastResult(null);

    try {
      const res = await onTaskCreated({
        youtube_url: youtubeUrl.trim(),
        upload_target: uploadTarget,
        auto_start: autoStart,
      });

      setLastResult(res);
      setYoutubeUrl('');
    } catch (err) {
      // 错误由父级 Toast 处理
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '12px',
          background: 'rgba(99, 102, 241, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.25rem',
        }}>
          ➕
        </div>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700' }}>新建搬运任务</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
            通过 RESTful API 创建单个视频或播放列表自动化下载与发布
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* YouTube 链接 */}
        <div className="form-group">
          <label className="form-label" htmlFor="task-url">
            YouTube 视频或播放列表链接
          </label>
          <input
            id="task-url"
            type="url"
            className="input-field"
            placeholder="https://www.youtube.com/watch?v=..."
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            disabled={isSubmitting}
            required
          />
          {isPlaylist ? (
            <div className="form-hint" style={{ color: 'var(--accent-cyan)' }}>
              ✨ 检测到播放列表 URL，后端将自动解析批量加入任务列表
            </div>
          ) : (
            <div className="form-hint">
              支持单个视频链接（watch?v=xxx）或包含多视频的 Playlist 链接
            </div>
          )}
        </div>

        {/* 目标平台选择 */}
        <div className="form-group">
          <label className="form-label">发布目标平台</label>
          <div className="platform-selector">
            <button
              type="button"
              className={`platform-btn ${uploadTarget === 'acfun' ? 'active' : ''}`}
              onClick={() => setUploadTarget('acfun')}
            >
              <span style={{ color: '#fd4c5a' }}>●</span> AcFun (A站)
            </button>
            <button
              type="button"
              className={`platform-btn ${uploadTarget === 'bilibili' ? 'active' : ''}`}
              onClick={() => setUploadTarget('bilibili')}
            >
              <span style={{ color: '#00aeec' }}>●</span> Bilibili (B站)
            </button>
            <button
              type="button"
              className={`platform-btn ${uploadTarget === 'both' ? 'active' : ''}`}
              onClick={() => setUploadTarget('both')}
            >
              <span style={{ color: '#c084fc' }}>●</span> 双平台同步
            </button>
          </div>
        </div>

        {/* 立即启动选项 */}
        <div className="form-group">
          <div
            className="switch-container"
            onClick={() => setAutoStart(!autoStart)}
            role="checkbox"
            aria-checked={autoStart}
          >
            <div className="switch-label-group">
              <span className="switch-title">创建后立即启动处理</span>
              <span className="switch-desc">自动触发下载、字幕翻译与后台流水线处理</span>
            </div>
            <div className={`switch-track ${autoStart ? 'active' : ''}`}>
              <div className="switch-thumb" />
            </div>
          </div>
        </div>

        {/* 提交按钮 */}
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', padding: '12px' }}
          disabled={isSubmitting || !youtubeUrl.trim()}
        >
          {isSubmitting ? (
            <>
              <span className="spinner" />
              正在提交任务至后端 API...
            </>
          ) : (
            '立即添加任务'
          )}
        </button>
      </form>

      {/* 提交结果反馈展示卡片 */}
      {lastResult && (
        <div style={{
          marginTop: '20px',
          padding: '16px',
          borderRadius: 'var(--radius-md)',
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          animation: 'slideUp 0.25s ease',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6ee7b7', fontWeight: '600', marginBottom: '8px', fontSize: '0.9rem' }}>
            <span>✓</span> {lastResult.message || '任务创建成功'}
          </div>
          {lastResult.task_id && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              任务 ID: <code style={{ fontFamily: 'var(--font-mono)', color: '#a5b4fc' }}>{lastResult.task_id}</code>
            </div>
          )}
          {lastResult.count !== undefined && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              解析到视频数: <strong style={{ color: 'white' }}>{lastResult.count}</strong> 个任务
            </div>
          )}
        </div>
      )}
    </div>
  );
}
