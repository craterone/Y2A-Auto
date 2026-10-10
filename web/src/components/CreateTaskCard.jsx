import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';

export function CreateTaskCard({ onTaskCreated, isSubmitting, setIsSubmitting }) {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [uploadTarget, setUploadTarget] = useState('acfun');
  const [autoStart, setAutoStart] = useState(true);
  const [lastResult, setLastResult] = useState(null);

  // Bilibili 合集状态
  const [seasons, setSeasons] = useState([]);
  const [loadingSeasons, setLoadingSeasons] = useState(false);
  const [selectedSeasonId, setSelectedSeasonId] = useState('');
  const hasFetchedRef = useRef(false);

  const isPlaylist = youtubeUrl.includes('playlist') || youtubeUrl.includes('list=');
  const isBilibiliTarget = uploadTarget === 'bilibili' || uploadTarget === 'both';

  // 加载用户已创建的合集列表
  const loadSeasons = useCallback(async (forceRefresh = false) => {
    setLoadingSeasons(true);
    try {
      const res = await api.getBilibiliSeasons(forceRefresh);
      if (res.success && Array.isArray(res.seasons)) {
        setSeasons(res.seasons);
      }
    } catch {
      // 忽略未登录等非阻断错误，保持界面可用
    } finally {
      setLoadingSeasons(false);
    }
  }, []);

  // 当选择 B 站或双平台且尚未加载合集时，自动获取一次
  useEffect(() => {
    if (isBilibiliTarget && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      loadSeasons(false);
    }
  }, [isBilibiliTarget, loadSeasons]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) return;

    setIsSubmitting(true);
    setLastResult(null);

    try {
      const matchedSeason = seasons.find((s) => String(s.season_id) === String(selectedSeasonId));
      const firstSection = matchedSeason?.sections?.[0];

      const res = await onTaskCreated({
        youtube_url: youtubeUrl.trim(),
        upload_target: uploadTarget,
        auto_start: autoStart,
        bilibili_season_id: matchedSeason ? matchedSeason.season_id : undefined,
        bilibili_section_id: firstSection ? firstSection.section_id : undefined,
        bilibili_season_title: matchedSeason ? matchedSeason.title : undefined,
      });

      setLastResult(res);
      setYoutubeUrl('');
    } catch {
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

        {/* Bilibili 合集选择（仅当发布目标包含 Bilibili 时显示） */}
        {isBilibiliTarget && (
          <div className="form-group" style={{
            background: 'rgba(56, 189, 248, 0.04)',
            border: '1px solid rgba(56, 189, 248, 0.2)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 14px',
            marginBottom: '16px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label className="form-label" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>📚</span> Bilibili 合集归属（可选）
              </label>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => loadSeasons(true)}
                disabled={loadingSeasons || isSubmitting}
                style={{ padding: '2px 8px', fontSize: '0.75rem', height: '26px' }}
                title="重新向 B 站拉取最新合集列表"
              >
                {loadingSeasons ? '加载中...' : '🔄 刷新合集'}
              </button>
            </div>

            <select
              className="input-field"
              value={selectedSeasonId}
              onChange={(e) => setSelectedSeasonId(e.target.value)}
              disabled={isSubmitting || loadingSeasons}
              style={{ width: '100%', background: 'rgba(15, 23, 42, 0.6)' }}
            >
              <option value="">不加入合集（普通独立投稿）</option>
              {seasons.map((s) => (
                <option key={s.season_id} value={s.season_id}>
                  {s.title} {s.ep_num !== undefined ? `(已收录 ${s.ep_num} 话)` : ''}
                </option>
              ))}
            </select>
            <div className="form-hint" style={{ marginTop: '6px' }}>
              {selectedSeasonId
                ? '✨ 视频成功发布至 B 站后，系统将自动调用接口将其收录至该合集。'
                : '选择已有合集后，任务投稿成功将自动追加至该合集；未配置则作为独立视频发布。'}
            </div>
          </div>
        )}

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
