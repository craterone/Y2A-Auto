import React, { useState } from 'react';
import { api } from '../api';

export function PlaylistMonitorList({
  monitors,
  isLoading,
  onRefresh,
  onViewTasks,
  showToast,
}) {
  const [checkingIds, setCheckingIds] = useState(new Set());
  const [deletingIds, setDeletingIds] = useState(new Set());
  const [togglingIds, setTogglingIds] = useState(new Set());

  // 立即触发检测
  const handleCheckNow = async (monitor) => {
    setCheckingIds((prev) => new Set(prev).add(monitor.id));
    try {
      const res = await api.checkPlaylistMonitorNow(monitor.id);
      if (res.success) {
        showToast(res.message || '检测成功，已扫描播放列表！', 'success');
        onRefresh();
      } else {
        showToast(res.message || '检测完成，但未发现新增视频', 'info');
      }
    } catch (err) {
      showToast(err.message || '立即检测失败', 'error');
    } finally {
      setCheckingIds((prev) => {
        const next = new Set(prev);
        next.delete(monitor.id);
        return next;
      });
    }
  };

  // 切换启用/禁用状态
  const handleToggleEnable = async (monitor) => {
    setTogglingIds((prev) => new Set(prev).add(monitor.id));
    try {
      const newEnabled = !monitor.enabled;
      await api.updatePlaylistMonitor(monitor.id, { enabled: newEnabled });
      showToast(newEnabled ? '已启用该播放列表监控' : '已暂停该播放列表监控', 'info');
      onRefresh();
    } catch (err) {
      showToast(err.message || '切换状态失败', 'error');
    } finally {
      setTogglingIds((prev) => {
        const next = new Set(prev);
        next.delete(monitor.id);
        return next;
      });
    }
  };

  // 删除监控
  const handleDelete = async (monitor) => {
    if (!window.confirm(`确定要删除播放列表监控【${monitor.title || monitor.playlist_id}】吗？\n（已创建的视频任务将被保留）`)) {
      return;
    }
    setDeletingIds((prev) => new Set(prev).add(monitor.id));
    try {
      const res = await api.deletePlaylistMonitor(monitor.id, false);
      if (res.success) {
        showToast('播放列表监控已成功删除', 'success');
        onRefresh();
      }
    } catch (err) {
      showToast(err.message || '删除监控失败', 'error');
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(monitor.id);
        return next;
      });
    }
  };

  // 格式化时间
  const formatTime = (timeStr) => {
    if (!timeStr) return '尚未检测';
    try {
      const normalized = timeStr.includes('T') ? timeStr : timeStr.replace(' ', 'T') + 'Z';
      const d = new Date(normalized);
      if (isNaN(d.getTime())) return timeStr;
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch {
      return timeStr;
    }
  };

  if (isLoading && monitors.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-dim)' }}>
        <div className="spinner" style={{ width: '28px', height: '28px', margin: '0 auto 12px' }} />
        <span>正在载入 Playlist 监控列表...</span>
      </div>
    );
  }

  if (monitors.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-dim)' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>📑</div>
        <p style={{ margin: 0, fontSize: '1rem', fontWeight: 500, color: '#f1f5f9' }}>
          暂无任何 Playlist 监控配置
        </p>
        <span style={{ fontSize: '0.825rem', opacity: 0.7, marginTop: '4px', display: 'block' }}>
          在上方输入 YouTube 播放列表 ID 或链接，即可开启全自动监控拉取与限流发布！
        </span>
      </div>
    );
  }

  return (
    <div className="playlist-monitor-list" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
          正在监控的播放列表 ({monitors.length})
        </h3>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onRefresh}
          disabled={isLoading}
          style={{ padding: '6px 14px', fontSize: '0.825rem' }}
        >
          🔄 刷新状态
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {monitors.map((m) => {
          const stats = m.task_stats || {};
          const isChecking = checkingIds.has(m.id);
          const isDeleting = deletingIds.has(m.id);
          const isToggling = togglingIds.has(m.id);

          return (
            <div
              key={m.id}
              className="card"
              style={{
                padding: '18px 20px',
                borderLeft: m.enabled ? '4px solid #38bdf8' : '4px solid #64748b',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                transition: 'transform 0.15s ease, border-color 0.15s ease',
              }}
            >
              {/* 卡片头部 */}
              <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', gap: '14px', flex: 1, minWidth: 0 }}>
                  {m.thumbnail_url ? (
                    <img
                      src={m.thumbnail_url}
                      alt="thumbnail"
                      style={{
                        width: '90px',
                        height: '56px',
                        objectFit: 'cover',
                        borderRadius: '6px',
                        border: '1px solid rgba(255,255,255,0.1)',
                      }}
                    />
                  ) : (
                    <div style={{
                      width: '90px',
                      height: '56px',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.05)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '1.5rem',
                    }}>
                      📑
                    </div>
                  )}

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        fontSize: '1.02rem',
                        fontWeight: 600,
                        color: '#f8fafc',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {m.title || `Playlist ${m.playlist_id}`}
                      </span>
                      <span className={`badge ${m.enabled ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.7rem' }}>
                        {m.enabled ? '监控中' : '已暂停'}
                      </span>
                    </div>

                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      fontSize: '0.78rem',
                      color: 'var(--text-dim)',
                      marginTop: '4px',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                    }}>
                      <span>ID: <code style={{ color: '#38bdf8' }}>{m.playlist_id}</code></span>
                      {m.channel_title && <span>频道: {m.channel_title}</span>}
                      <span>投稿目标: <strong style={{ color: '#38bdf8' }}>BILIBILI</strong></span>
                      <span className={`badge ${m.auto_upload !== false && m.auto_upload !== 0 ? 'badge-success' : 'badge-neutral'}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                        {m.auto_upload !== false && m.auto_upload !== 0 ? '🚀 自动投稿' : '⏸ 手动发布'}
                      </span>
                      <span>已探测总视频: <strong>{m.total_videos_found || 0}</strong></span>
                    </div>

                    {Boolean(m.custom_description) && (
                      <div style={{
                        marginTop: '6px',
                        fontSize: '0.75rem',
                        color: 'var(--text-secondary, #cbd5e1)',
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px dashed rgba(255, 255, 255, 0.1)',
                        borderRadius: '4px',
                        padding: '4px 8px',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '650px',
                      }} title={m.custom_description}>
                        📝 统一简介: {m.custom_description}
                      </div>
                    )}
                  </div>
                </div>

                {/* 状态切换与删除 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleToggleEnable(m)}
                    disabled={isToggling}
                    style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    title={m.enabled ? '暂停监控' : '恢复监控'}
                  >
                    {isToggling ? '...' : m.enabled ? '⏸ 暂停' : '▶ 启用'}
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleDelete(m)}
                    disabled={isDeleting}
                    style={{ padding: '6px 10px', fontSize: '0.8rem', color: '#f87171' }}
                    title="删除监控"
                  >
                    🗑
                  </button>
                </div>
              </div>

              {/* 核心配置指标与任务统计行 */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '10px',
                background: 'rgba(255, 255, 255, 0.02)',
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                fontSize: '0.8rem',
              }}>
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>⏱️ 检测周期</span>
                  <strong style={{ color: '#38bdf8' }}>{m.check_interval_minutes} 分钟</strong>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>⚡ 最大并发 (Task)</span>
                  <strong style={{ color: '#f59e0b' }}>{m.max_concurrency} 个同时运行</strong>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>🔄 运行中 / 排队</span>
                  <span>
                    <strong style={{ color: '#38bdf8' }}>{stats.running || 0}</strong>
                    {' / '}
                    <strong style={{ color: '#facc15' }}>{stats.pending || 0}</strong>
                  </span>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>✅ 已完成 / 失败</span>
                  <span>
                    <strong style={{ color: '#4ade80' }}>{stats.completed || 0}</strong>
                    {' / '}
                    <strong style={{ color: stats.failed > 0 ? '#f87171' : 'var(--text-dim)' }}>{stats.failed || 0}</strong>
                  </span>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>🕒 最近一次检测</span>
                  <span style={{ color: 'var(--text-dim)' }}>{formatTime(m.last_checked_at)}</span>
                </div>
              </div>

              {/* 底部动作工具条 */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingTop: '4px',
                borderTop: '1px solid rgba(255, 255, 255, 0.04)',
              }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  {m.last_check_message ? (
                    <span>状态: {m.last_check_message}</span>
                  ) : (
                    <span>已就绪，下次轮询将自动增量检查</span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleCheckNow(m)}
                    disabled={isChecking}
                    style={{
                      padding: '6px 14px',
                      fontSize: '0.8rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    {isChecking ? (
                      <>
                        <div className="spinner" style={{ width: '12px', height: '12px' }} />
                        <span>正在检测...</span>
                      </>
                    ) : (
                      <>
                        <span>⚡ 立即检测</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => onViewTasks(m)}
                    style={{
                      padding: '6px 16px',
                      fontSize: '0.8rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                    }}
                  >
                    <span>📋 查看该 Playlist 所有 Task</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
