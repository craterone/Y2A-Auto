import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';

export function PlaylistMonitorCard({ onMonitorCreated, showToast }) {
  const [playlistId, setPlaylistId] = useState('');
  const [checkInterval, setCheckInterval] = useState(30);
  const [maxConcurrency, setMaxConcurrency] = useState(1);
  const [autoUpload, setAutoUpload] = useState(true);
  const [customDescription, setCustomDescription] = useState('');
  const [customTitle, setCustomTitle] = useState('');
  
  // Bilibili 合集状态
  const [seasons, setSeasons] = useState([]);
  const [loadingSeasons, setLoadingSeasons] = useState(false);
  const [selectedSeasonId, setSelectedSeasonId] = useState('');
  const hasFetchedRef = useRef(false);

  const [previewData, setPreviewData] = useState(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 加载用户已创建的合集列表
  const loadSeasons = useCallback(async (forceRefresh = false) => {
    setLoadingSeasons(true);
    try {
      const res = await api.getBilibiliSeasons(forceRefresh);
      if (res.success && Array.isArray(res.seasons)) {
        setSeasons(res.seasons);
      }
    } catch {
      // 忽略未登录等非阻断错误
    } finally {
      setLoadingSeasons(false);
    }
  }, []);

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      loadSeasons(false);
    }
  }, [loadSeasons]);

  // 尝试自动提取播放列表ID
  const handleInputChange = (e) => {
    const val = e.target.value;
    setPlaylistId(val);
    setPreviewData(null);
  };

  // 预览播放列表信息
  const handlePreview = async () => {
    if (!playlistId.trim()) {
      showToast('请输入 YouTube Playlist ID 或链接', 'warning');
      return;
    }
    setIsPreviewing(true);
    try {
      const res = await api.previewPlaylist(playlistId.trim());
      if (res.success && res.preview) {
        setPreviewData(res.preview);
        if (!customTitle && res.preview.title) {
          setCustomTitle(res.preview.title);
        }
        showToast(`已成功获取播放列表信息: ${res.preview.title}`, 'success');
      }
    } catch (err) {
      showToast(err.message || '预览获取失败，请确认 API Key 或播放列表 ID 是否正确', 'error');
    } finally {
      setIsPreviewing(false);
    }
  };

  // 提交添加监控
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!playlistId.trim()) {
      showToast('请输入播放列表 ID 或完整链接', 'warning');
      return;
    }

    const interval = parseInt(checkInterval, 10);
    if (isNaN(interval) || interval < 5) {
      showToast('检测时间间隔不能少于 5 分钟', 'warning');
      return;
    }

    const concurrency = parseInt(maxConcurrency, 10);
    if (isNaN(concurrency) || concurrency < 1) {
      showToast('最大并发任务数至少为 1', 'warning');
      return;
    }

    setIsSubmitting(true);
    try {
      const matchedSeason = seasons.find((s) => String(s.season_id) === String(selectedSeasonId));
      const firstSection = matchedSeason?.sections?.[0];

      const res = await api.createPlaylistMonitor({
        playlist_id: playlistId.trim(),
        check_interval_minutes: interval,
        max_concurrency: concurrency,
        upload_target: 'bilibili',
        auto_upload: autoUpload,
        custom_description: customDescription.trim(),
        enabled: true,
        custom_title: customTitle.trim() || undefined,
        bilibili_season_id: matchedSeason ? matchedSeason.season_id : undefined,
        bilibili_section_id: firstSection ? firstSection.section_id : undefined,
        bilibili_season_title: matchedSeason ? matchedSeason.title : undefined,
      });

      if (res.success) {
        showToast(res.message || 'Playlist 监控添加成功，系统将自动检测拉取！', 'success');
        setPlaylistId('');
        setCustomTitle('');
        setCustomDescription('');
        setAutoUpload(true);
        setSelectedSeasonId('');
        setPreviewData(null);
        setCheckInterval(30);
        setMaxConcurrency(1);
        if (onMonitorCreated) {
          onMonitorCreated(res.monitor);
        }
      }
    } catch (err) {
      showToast(err.message || '创建监控失败', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="card playlist-monitor-card" style={{ marginBottom: '24px' }}>
      <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.4rem' }}>📑</span>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>添加 YouTube Playlist 监控</h2>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-dim)' }}>
              自动定时轮询播放列表新视频，按设定并发数调度并发布投稿
            </p>
          </div>
        </div>
        <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
          YouTube API v3
        </span>
      </div>

      <form onSubmit={handleSubmit} style={{ marginTop: '16px' }}>
        {/* Playlist ID 输入行 */}
        <div className="form-group" style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
            YouTube Playlist ID 或 播放列表链接 <span style={{ color: '#ef4444' }}>*</span>
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="input-field"
              placeholder="例如: PLbpi6ZahtOH6Blw3RGY3973uEI836_QvB 或 https://www.youtube.com/playlist?list=..."
              value={playlistId}
              onChange={handleInputChange}
              disabled={isSubmitting}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handlePreview}
              disabled={isPreviewing || !playlistId.trim()}
              style={{ whiteSpace: 'nowrap', padding: '0 16px' }}
            >
              {isPreviewing ? '解析中...' : '🔍 解析列表'}
            </button>
          </div>
        </div>

        {/* 预览结果卡片 */}
        {previewData && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '10px',
            padding: '12px 16px',
            marginBottom: '16px',
            display: 'flex',
            gap: '14px',
            alignItems: 'center',
          }}>
            {previewData.thumbnail_url && (
              <img
                src={previewData.thumbnail_url}
                alt="cover"
                style={{ width: '88px', height: '52px', objectFit: 'cover', borderRadius: '6px' }}
              />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {previewData.title}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                频道: {previewData.channel_title || '未知'} · 共计 {previewData.item_count || 0} 个视频
              </div>
            </div>
            <span style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.15)', color: '#4ade80' }}>
              有效播放列表
            </span>
          </div>
        )}

        {/* 自定义名称 */}
        <div className="form-group" style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
            监控标题备注（可选）
          </label>
          <input
            type="text"
            className="input-field"
            placeholder="留空则自动使用播放列表原标题"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        {/* 参数设置栅格：检测时间、最大并发、投稿目标 */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '20px'
        }}>
          {/* 检测时间 */}
          <div className="form-group">
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              ⏱️ 检测时间间隔 (分钟)
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="number"
                min="5"
                max="1440"
                className="input-field"
                value={checkInterval}
                onChange={(e) => setCheckInterval(e.target.value)}
                disabled={isSubmitting}
                style={{ width: '100%' }}
              />
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
              默认 30 分钟轮询一次新视频
            </span>
          </div>

          {/* 最大并发 */}
          <div className="form-group">
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              ⚡ 最大并发任务数
            </label>
            <input
              type="number"
              min="1"
              max="10"
              className="input-field"
              value={maxConcurrency}
              onChange={(e) => setMaxConcurrency(e.target.value)}
              disabled={isSubmitting}
              style={{ width: '100%' }}
            />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
              该 Playlist 下同时处于运行中(Task)的上限
            </span>
          </div>

          {/* 默认投稿平台 */}
          <div className="form-group">
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              🎯 投稿目标平台
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 12px',
              background: 'rgba(56, 189, 248, 0.08)',
              borderRadius: '6px',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              color: '#38bdf8',
              fontSize: '0.88rem',
              fontWeight: 500,
            }}>
              <span>📺 哔哩哔哩 (Bilibili)</span>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', fontSize: '0.7rem' }}>
                默认专属
              </span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
              播放列表新视频将默认发布投稿至 B站
            </span>
          </div>
        </div>

        {/* 自动投稿开关 */}
        <div className="form-group" style={{
          marginBottom: '16px',
          background: 'rgba(255, 255, 255, 0.02)',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.88rem', fontWeight: 500 }}>
            <input
              type="checkbox"
              checked={autoUpload}
              onChange={(e) => setAutoUpload(e.target.checked)}
              disabled={isSubmitting}
              style={{ width: '16px', height: '16px', cursor: 'pointer' }}
            />
            <span style={{ color: '#f1f5f9' }}>🚀 启用自动投稿（默认开启）</span>
          </label>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '26px', marginTop: '4px', display: 'block' }}>
            开启后，检测到的新视频将在前置处理完成后自动提交投稿至 Bilibili；若关闭，视频处理完毕后将停留在“准备上传”状态待人工确认发布。
          </span>
        </div>

        {/* 关联 Bilibili 合集配置 */}
        <div className="form-group" style={{
          marginBottom: '16px',
          background: 'rgba(56, 189, 248, 0.04)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
          padding: '14px 16px',
          borderRadius: '8px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 500, margin: 0 }}>
              <span>📚</span> 绑定 Bilibili 投稿合集（可选）
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
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '6px', display: 'block' }}>
            {selectedSeasonId
              ? '✨ 绑定后，该播放列表监控自动拉取并发布的所有视频，都将归入此合集中！'
              : '选择合集后，监控自动发布的视频将自动收录入该合集；未配置则作为独立视频发布。'}
          </span>
        </div>

        {/* 统一投稿简介 (Description) */}
        <div className="form-group" style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
            📝 统一投稿简介 (Description，可选)
          </label>
          <textarea
            className="input-field"
            rows={3}
            placeholder="可选。配置后，该播放列表下的所有视频在投稿时都将统一使用此简介，并自动跳过大模型简介翻译"
            value={customDescription}
            onChange={(e) => setCustomDescription(e.target.value)}
            disabled={isSubmitting}
            style={{ width: '100%', resize: 'vertical' }}
          />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
            若留空，则使用原视频简介或由 AI 翻译生成简介
          </span>
        </div>

        {/* 底部提交动作 */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isSubmitting || !playlistId.trim()}
            style={{
              padding: '10px 24px',
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {isSubmitting ? (
              <>
                <div className="spinner" style={{ width: '14px', height: '14px' }} />
                <span>正在添加监控...</span>
              </>
            ) : (
              <>
                <span>🚀 添加并启动监控</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
