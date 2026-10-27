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
  const [editingMonitor, setEditingMonitor] = useState(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const handleOpenEdit = (monitor) => {
    setEditingMonitor({
      id: monitor.id,
      title: monitor.title || '',
      check_interval_minutes: monitor.check_interval_minutes || 30,
      max_concurrency: monitor.max_concurrency || 1,
      task_interval_minutes: monitor.task_interval_minutes !== undefined ? monitor.task_interval_minutes : 15,
      max_import_per_check: monitor.max_import_per_check !== undefined ? monitor.max_import_per_check : 10,
      import_order: monitor.import_order || 'asc',
      auto_upload: monitor.auto_upload !== false && monitor.auto_upload !== 0,
      translate_title: Boolean(monitor.translate_title),
      custom_description: monitor.custom_description || '',
      title_pattern: monitor.title_pattern || '',
      title_template: monitor.title_template || '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editingMonitor) return;
    setIsSavingEdit(true);
    try {
      const res = await api.updatePlaylistMonitor(editingMonitor.id, {
        title: editingMonitor.title,
        check_interval_minutes: parseInt(editingMonitor.check_interval_minutes, 10) || 30,
        max_concurrency: parseInt(editingMonitor.max_concurrency, 10) || 1,
        task_interval_minutes: parseInt(editingMonitor.task_interval_minutes, 10) || 0,
        max_import_per_check: parseInt(editingMonitor.max_import_per_check, 10) || 0,
        import_order: editingMonitor.import_order,
        auto_upload: editingMonitor.auto_upload,
        translate_title: editingMonitor.translate_title,
        custom_description: editingMonitor.custom_description,
        title_pattern: editingMonitor.title_pattern,
        title_template: editingMonitor.title_template,
      });
      if (res.success) {
        showToast('播放列表监控配置已更新', 'success');
        setEditingMonitor(null);
        onRefresh();
      }
    } catch (err) {
      showToast(err.message || '更新配置失败', 'error');
    } finally {
      setIsSavingEdit(false);
    }
  };

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
                      <span className={`badge ${m.translate_title ? 'badge-info' : 'badge-neutral'}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                        {m.translate_title ? '🌐 自动翻译标题' : '🏷️ 原标题不变'}
                      </span>
                      <span>已探测总视频: <strong>{m.total_videos_found || 0}</strong></span>
                      {Boolean(m.bilibili_season_title) && (
                        <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: '0.68rem', padding: '2px 6px' }}>
                          📚 合集: {m.bilibili_season_title}
                        </span>
                      )}
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

                    {Boolean(m.title_pattern) && Boolean(m.title_template) && (
                      <div style={{
                        marginTop: '4px',
                        fontSize: '0.75rem',
                        color: '#c084fc',
                        background: 'rgba(168, 85, 247, 0.06)',
                        border: '1px dashed rgba(168, 85, 247, 0.2)',
                        borderRadius: '4px',
                        padding: '4px 8px',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '650px',
                      }} title={`匹配: ${m.title_pattern} → 替换: ${m.title_template}`}>
                        🔤 标题替换: {m.title_template}
                      </div>
                    )}
                  </div>
                </div>

                {/* 状态切换、配置与删除 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleOpenEdit(m)}
                    style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    title="修改监控与防风控参数"
                  >
                    ⚙️ 配置
                  </button>

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
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>⚡ 最大并发</span>
                  <strong style={{ color: '#f59e0b' }}>{m.max_concurrency} 个</strong>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>
                    🛡️ 任务间隔 <span style={{ color: '#facc15' }}>(防风控)</span>
                  </span>
                  <strong style={{ color: '#facc15' }}>
                    {m.task_interval_minutes !== undefined && m.task_interval_minutes !== null ? `${m.task_interval_minutes} 分钟` : '15 分钟'}
                  </strong>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>📦 单次导入</span>
                  <strong style={{ color: '#a78bfa' }}>
                    {m.max_import_per_check ? `${m.max_import_per_check} 个` : '全量'}
                  </strong>
                </div>

                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>↕️ 导入顺序</span>
                  <strong style={{ color: '#94a3b8' }}>
                    {m.import_order === 'desc' ? '最新优先' : '从旧到新'}
                  </strong>
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

      {/* 参数修改配置弹窗 Modal */}
      {Boolean(editingMonitor) && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px',
        }}>
          <div className="card" style={{
            width: '100%',
            maxWidth: '560px',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                ⚙️ 修改 Playlist 监控与防风控配置
              </h3>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setEditingMonitor(null)}
                style={{ padding: '4px 8px', fontSize: '0.8rem' }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                  自定义名称 / 备注
                </label>
                <input
                  type="text"
                  className="input-field"
                  value={editingMonitor.title}
                  onChange={(e) => setEditingMonitor({ ...editingMonitor, title: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                    ⏱️ 检测周期 (分钟)
                  </label>
                  <input
                    type="number"
                    min="5"
                    className="input-field"
                    value={editingMonitor.check_interval_minutes}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, check_interval_minutes: e.target.value })}
                    style={{ width: '100%' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                    ⚡ 最大并发 (Task)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    className="input-field"
                    value={editingMonitor.max_concurrency}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, max_concurrency: e.target.value })}
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              {/* 防风控关键设置块 */}
              <div style={{
                background: 'rgba(234, 179, 8, 0.05)',
                border: '1px solid rgba(234, 179, 8, 0.2)',
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                <div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.825rem', marginBottom: '4px', fontWeight: 500, color: '#facc15' }}>
                    <span>🛡️ 任务执行间隔 (分钟，防 B 站风控)</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1440"
                    className="input-field"
                    value={editingMonitor.task_interval_minutes}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, task_interval_minutes: e.target.value })}
                    style={{ width: '100%' }}
                  />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px', display: 'block' }}>
                    上一个任务完成/投稿后冷却多长时间再执行下一个（建议 15~30 分钟，0 为无间隔）
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                      📦 单次导入上限 (个)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="500"
                      className="input-field"
                      value={editingMonitor.max_import_per_check}
                      onChange={(e) => setEditingMonitor({ ...editingMonitor, max_import_per_check: e.target.value })}
                      style={{ width: '100%' }}
                    />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px', display: 'block' }}>
                      0 为不限制/全量导入
                    </span>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                      ↕️ 导入视频顺序
                    </label>
                    <select
                      className="input-field"
                      value={editingMonitor.import_order}
                      onChange={(e) => setEditingMonitor({ ...editingMonitor, import_order: e.target.value })}
                      style={{ width: '100%', height: '36px' }}
                    >
                      <option value="asc">正序 (从旧到新)</option>
                      <option value="desc">倒序 (最新优先)</option>
                    </select>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px', display: 'block' }}>
                      首集优先或最新优先
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={editingMonitor.auto_upload}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, auto_upload: e.target.checked })}
                    style={{ width: '16px', height: '16px' }}
                  />
                  <span>🚀 自动发布投稿到 Bilibili</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={editingMonitor.translate_title}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, translate_title: e.target.checked })}
                    style={{ width: '16px', height: '16px' }}
                  />
                  <span>🌐 自动翻译标题（默认关闭）</span>
                </label>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginLeft: '24px', display: 'block', marginTop: '-4px' }}>
                  开启后通过 AI 翻译视频标题为中文；关闭后保留视频原标题发布（或优先使用下方正则替换规则）
                </span>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
                  统一投稿简介 (可选覆盖)
                </label>
                <textarea
                  className="input-field"
                  rows={3}
                  value={editingMonitor.custom_description}
                  onChange={(e) => setEditingMonitor({ ...editingMonitor, custom_description: e.target.value })}
                  style={{ width: '100%', resize: 'vertical' }}
                  placeholder="留空则使用视频原生简介或AI翻译简介"
                />
              </div>

              {/* 标题替换规则 */}
              <div style={{
                background: 'rgba(168, 85, 247, 0.05)',
                border: '1px solid rgba(168, 85, 247, 0.2)',
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.825rem', fontWeight: 500, color: '#c084fc', marginBottom: 0 }}>
                  <span>🔤 标题格式替换规则（可选）</span>
                  <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', fontSize: '0.6rem', padding: '1px 4px' }}>正则</span>
                </label>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '3px' }}>
                    匹配模式（正则表达式）
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder={'例如: Learn English.*Part (\\d+)'}
                    value={editingMonitor.title_pattern}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, title_pattern: e.target.value })}
                    style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.82rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '3px' }}>
                    替换模板（{'用 {1} 引用捕获组'})
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder={'例如: 跟着《动物庄园》学英语｜深度精听第 {1} 集'}
                    value={editingMonitor.title_template}
                    onChange={(e) => setEditingMonitor({ ...editingMonitor, title_template: e.target.value })}
                    style={{ width: '100%', fontSize: '0.82rem' }}
                  />
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                  配置后自动替代标题 AI 翻译，未匹配的标题仍走 AI 翻译
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditingMonitor(null)}
                  disabled={isSavingEdit}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSaveEdit}
                  disabled={isSavingEdit}
                >
                  {isSavingEdit ? '保存中...' : '💾 保存修改'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
