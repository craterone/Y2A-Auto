import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

export function PlaylistTasksModal({ monitor, onClose, showToast }) {
  const [tasks, setTasks] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(15);
  const [order, setOrder] = useState('desc'); // 'desc' (时间倒序) 或 'asc' (时间顺序)
  const [statusFilter, setStatusFilter] = useState('');
  const [stats, setStats] = useState({});
  const [isLoading, setIsLoading] = useState(false);

  // 拉取该 playlist 的任务
  const fetchTasks = useCallback(async () => {
    if (!monitor) return;
    setIsLoading(true);
    try {
      const res = await api.getPlaylistTasks(monitor.id, {
        order,
        page,
        per_page: perPage,
        status: statusFilter || undefined,
      });

      if (res.success) {
        setTasks(res.tasks || []);
        setTotal(res.total || 0);
        setStats(res.stats || {});
      }
    } catch (err) {
      showToast(err.message || '获取播放列表任务失败', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [monitor, order, page, perPage, statusFilter, showToast]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // 获取状态显示样式
  const getStatusBadge = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'completed') {
      return <span className="badge badge-success">已完成</span>;
    }
    if (s === 'failed' || s.includes('error')) {
      return <span className="badge badge-danger">处理失败</span>;
    }
    if (s === 'pending') {
      return <span className="badge badge-warning">排队等待中</span>;
    }
    return (
      <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        <span className="spinner" style={{ width: '8px', height: '8px' }} />
        {status}
      </span>
    );
  };

  // 格式化时间
  const formatTime = (timeStr) => {
    if (!timeStr) return '--';
    try {
      const normalized = timeStr.includes('T') ? timeStr : timeStr.replace(' ', 'T') + 'Z';
      const d = new Date(normalized);
      if (isNaN(d.getTime())) return timeStr;
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch {
      return timeStr;
    }
  };

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px',
    }}>
      <div className="card modal-content" style={{
        maxWidth: '960px',
        width: '100%',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        padding: 0,
      }}>
        {/* Modal 头部 */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '1.2rem' }}>📑</span>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600 }}>
                {monitor?.title || '播放列表任务'}
              </h3>
              <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.08)', color: 'var(--text-dim)' }}>
                ID: {monitor?.playlist_id}
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              最大并发: {monitor?.max_concurrency || 1} · 检测周期: {monitor?.check_interval_minutes || 30} mins
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.85rem' }}
          >
            ✕ 关闭
          </button>
        </div>

        {/* 顶部统计与排序控制栏 */}
        <div style={{
          padding: '14px 24px',
          background: 'rgba(255, 255, 255, 0.02)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {/* 任务状态统计 */}
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.82rem' }}>
            <span style={{ color: 'var(--text-dim)' }}>
              总任务: <strong style={{ color: '#f1f5f9' }}>{stats.total ?? total}</strong>
            </span>
            <span style={{ color: '#38bdf8' }}>
              运行中: <strong>{stats.running ?? 0}</strong>
            </span>
            <span style={{ color: '#facc15' }}>
              排队: <strong>{stats.pending ?? 0}</strong>
            </span>
            <span style={{ color: '#4ade80' }}>
              已完成: <strong>{stats.completed ?? 0}</strong>
            </span>
            {stats.failed > 0 && (
              <span style={{ color: '#f87171' }}>
                失败: <strong>{stats.failed}</strong>
              </span>
            )}
          </div>

          {/* 排序与状态筛选控件 */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {/* 视频发布时间倒序/顺序切换 */}
            <div style={{
              display: 'inline-flex',
              background: 'rgba(255, 255, 255, 0.06)',
              borderRadius: '8px',
              padding: '2px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}>
              <button
                type="button"
                onClick={() => { setOrder('desc'); setPage(1); }}
                style={{
                  background: order === 'desc' ? 'var(--primary-color, #38bdf8)' : 'transparent',
                  color: order === 'desc' ? '#0f172a' : 'var(--text-dim)',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '5px 12px',
                  fontSize: '0.78rem',
                  fontWeight: order === 'desc' ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                ⏱️ 按视频发布时间倒序 (最新在前)
              </button>
              <button
                type="button"
                onClick={() => { setOrder('asc'); setPage(1); }}
                style={{
                  background: order === 'asc' ? 'var(--primary-color, #38bdf8)' : 'transparent',
                  color: order === 'asc' ? '#0f172a' : 'var(--text-dim)',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '5px 12px',
                  fontSize: '0.78rem',
                  fontWeight: order === 'asc' ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                ⏳ 按视频发布时间正序 (最早在前)
              </button>
            </div>

            {/* 状态过滤器 */}
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="input-field"
              style={{ padding: '5px 10px', fontSize: '0.8rem', width: '120px' }}
            >
              <option value="">全部状态</option>
              <option value="pending">仅看排队</option>
              <option value="completed">仅看完成</option>
              <option value="failed">仅看失败</option>
            </select>

            {/* 刷新按钮 */}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={fetchTasks}
              disabled={isLoading}
              style={{ padding: '5px 10px', fontSize: '0.8rem' }}
              title="刷新列表"
            >
              🔄
            </button>
          </div>
        </div>

        {/* Task 列表主体内容 */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 24px',
        }}>
          {isLoading && tasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-dim)' }}>
              <div className="spinner" style={{ width: '28px', height: '28px', margin: '0 auto 12px' }} />
              <span>正在加载该播放列表任务...</span>
            </div>
          ) : tasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-dim)' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>📭</div>
              <p style={{ margin: 0, fontSize: '0.95rem' }}>该 Playlist 下暂未生成任何任务</p>
              <span style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                点击外部的“立即检测”按钮可立刻扫描抓取该播放列表中的视频
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {tasks.map((task) => (
                <div
                  key={task.id}
                  style={{
                    background: 'rgba(255, 255, 255, 0.025)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    transition: 'border-color 0.2s',
                  }}
                >
                  {/* 状态徽标 */}
                  <div style={{ minWidth: '95px' }}>
                    {getStatusBadge(task.status)}
                  </div>

                  {/* 视频信息 */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '0.9rem',
                      fontWeight: 500,
                      color: '#f8fafc',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {task.video_title_translated || task.video_title_original || task.youtube_url}
                    </div>

                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      fontSize: '0.75rem',
                      color: 'var(--text-dim)',
                      marginTop: '4px',
                      flexWrap: 'wrap',
                    }}>
                      <span>任务ID: {task.id.slice(0, 8)}...</span>
                      <span>平台: {task.upload_target?.toUpperCase() || 'BILIBILI'}</span>
                      {Boolean(task.video_published_at || task.videoPublishedAt) && (
                        <span style={{ color: '#38bdf8' }}>
                          📅 发布时间: <strong>{formatTime(task.video_published_at || task.videoPublishedAt)}</strong>
                        </span>
                      )}
                      <span>🕒 入库时间: {formatTime(task.created_at)}</span>
                      {task.error_message && (
                        <span style={{ color: '#f87171' }} title={task.error_message}>
                          错误: {task.error_message.slice(0, 30)}...
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 原始外链 */}
                  <div>
                    <a
                      href={task.youtube_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '0.75rem', textDecoration: 'none' }}
                    >
                      📺 观看
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 分页控制栏 */}
        {total > perPage && (
          <div style={{
            padding: '12px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.85rem',
            color: 'var(--text-dim)',
          }}>
            <span>第 {page} 页 / 共 {Math.ceil(total / perPage)} 页 (共 {total} 条)</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                style={{ padding: '4px 12px' }}
              >
                上一页
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page * perPage >= total || isLoading}
                onClick={() => setPage((p) => p + 1)}
                style={{ padding: '4px 12px' }}
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
