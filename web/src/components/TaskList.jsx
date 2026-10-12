import React, { useState } from 'react';
import { Pagination } from './Pagination';

const STATUS_MAP = {
  pending: { label: '排队中', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)' },
  downloading: { label: '下载中', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' },
  downloaded: { label: '已下载', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.15)' },
  extracting_audio: { label: '提取音频', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)' },
  transcribing: { label: '语音识别', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)' },
  translating: { label: '翻译中', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.15)' },
  generating_subtitles: { label: '生成字幕', color: '#e879f9', bg: 'rgba(232, 121, 249, 0.15)' },
  burning_subtitles: { label: '压制字幕', color: '#f472b6', bg: 'rgba(244, 114, 182, 0.15)' },
  awaiting_review: { label: '待人工审核', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)' },
  uploading: { label: '上传中', color: '#fb923c', bg: 'rgba(251, 146, 60, 0.15)' },
  completed: { label: '已完成', color: '#34d399', bg: 'rgba(52, 211, 153, 0.15)' },
  failed: { label: '失败', color: '#f87171', bg: 'rgba(248, 113, 113, 0.15)' },
  abandoned: { label: '已废弃', color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)' },
};

export function TaskList({
  tasks,
  total,
  page = 1,
  pageSize = 20,
  totalPages = 1,
  loading,
  onRefresh,
  onDelete,
  onClearAll,
  onPageChange,
  onPageSizeChange,
}) {
  const [deletingId, setDeletingId] = useState(null);
  const [isClearing, setIsClearing] = useState(false);

  const getStatusBadge = (status) => {
    const s = STATUS_MAP[status] || {
      label: status || '未知',
      color: '#cbd5e1',
      bg: 'rgba(203, 213, 225, 0.15)',
    };
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: s.color,
          backgroundColor: s.bg,
          border: `1px solid ${s.color}33`,
        }}
      >
        {s.label}
      </span>
    );
  };

  const getPlatformBadge = (target) => {
    if (target === 'both') {
      return <span className="badge badge-both">双平台</span>;
    }
    if (target === 'bilibili') {
      return <span className="badge badge-bilibili">B站</span>;
    }
    return <span className="badge badge-acfun">A站</span>;
  };

  const copyId = (id) => {
    navigator.clipboard?.writeText(id);
  };

  const handleDelete = async (task) => {
    const taskName = task.video_title_translated || task.video_title || task.id;
    const confirmed = window.confirm(`确定要删除任务「${taskName}」吗？\n该操作会同时清理本地相关下载文件。`);
    if (!confirmed) return;

    if (onDelete) {
      setDeletingId(task.id);
      try {
        await onDelete(task.id);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const handleClearAll = async () => {
    const taskCount = total || tasks.length;
    const confirmed = window.confirm(
      `确定要清除全部 ${taskCount} 个任务吗？\n所有任务记录以及本地下载的媒体文件将被彻底删除，此操作不可撤销！`
    );
    if (!confirmed) return;

    if (onClearAll) {
      setIsClearing(true);
      try {
        await onClearAll();
      } finally {
        setIsClearing(false);
      }
    }
  };

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: '700' }}>近期任务</h2>
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '9999px',
              background: 'var(--bg-glass)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-muted)'
            }}>
              总计 {total}
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            通过 GET /api/tasks 实时获取
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {(total > 0 || tasks.length > 0) && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={handleClearAll}
              disabled={isClearing || loading}
              style={{ padding: '6px 14px', fontSize: '0.825rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              title="清除所有任务及关联的下载文件"
            >
              {isClearing ? (
                <>
                  <span className="spinner" style={{ width: '12px', height: '12px' }} />
                  清空中...
                </>
              ) : (
                '🗑️ 清除所有任务'
              )}
            </button>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={onRefresh}
            disabled={loading || isClearing}
            style={{ padding: '6px 14px', fontSize: '0.825rem' }}
          >
            {loading ? (
              <>
                <span className="spinner" style={{ width: '14px', height: '14px' }} />
                刷新中
              </>
            ) : (
              '↻ 刷新列表'
            )}
          </button>
        </div>
      </div>


      {tasks.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '48px 20px',
          color: 'var(--text-dim)',
          background: 'rgba(255, 255, 255, 0.01)',
          borderRadius: 'var(--radius-md)',
          border: '1px dashed var(--border-color)',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>📂</div>
          <div style={{ fontSize: '0.95rem', fontWeight: '500', color: 'var(--text-muted)' }}>暂无任务记录</div>
          <div style={{ fontSize: '0.8rem' }}>在左侧输入 YouTube 链接添加您的第一个搬运任务吧</div>
        </div>
      ) : (
        <div className="task-table-wrapper">
          <table className="task-table">
            <thead>
              <tr>
                <th>任务状态</th>
                <th>发布目标</th>
                <th>视频源 / 标题</th>
                <th>创建时间</th>
                <th style={{ textAlign: 'right' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>{getStatusBadge(task.status)}</td>
                  <td>
                    {getPlatformBadge(task.upload_target)}
                    {task.bilibili_season_title && (
                      <div style={{ marginTop: '4px' }}>
                        <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: '0.68rem', padding: '1px 5px', display: 'inline-block' }}>
                          📚 {task.bilibili_season_title}
                        </span>
                      </div>
                    )}
                  </td>
                  <td>
                    <div style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>
                        {task.video_title_translated || task.video_title || task.youtube_url}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {task.id.slice(0, 16)}...
                    </div>
                  </td>
                  <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                    {task.created_at || '刚刚'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', alignItems: 'center' }}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => copyId(task.id)}
                        title="复制完整任务ID"
                        style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      >
                        复制 ID
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => handleDelete(task)}
                        disabled={deletingId === task.id}
                        title="删除该任务及其文件"
                        style={{
                          padding: '4px 8px',
                          fontSize: '0.75rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        {deletingId === task.id ? (
                          <>
                            <span className="spinner" style={{ width: '10px', height: '10px' }} />
                            删除中
                          </>
                        ) : (
                          '删除'
                        )}
                      </button>
                    </div>
                  </td>

                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 分页控制栏 */}
      {tasks.length > 0 && (
        <Pagination
          currentPage={page}
          totalItems={total}
          pageSize={pageSize}
          totalPages={totalPages}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          loading={loading}
        />
      )}
    </div>
  );
}
