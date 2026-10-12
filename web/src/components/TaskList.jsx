import React, { useState } from 'react';
import { Pagination } from './Pagination';

const STATUS_MAP = {
  pending: { label: '排队中', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)', icon: '⏳' },
  fetching_info: { label: '采集信息中', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)', icon: '🔍' },
  info_fetched: { label: '已获取信息', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.15)', icon: '📋' },
  downloading: { label: '正在下载', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)', icon: '⬇️' },
  downloaded: { label: '下载完成', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.15)', icon: '📦' },
  extracting_audio: { label: '提取音频', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)', icon: '🎵' },
  asr_transcribing: { label: '语音识别', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)', icon: '🎙️' },
  transcribing: { label: '语音识别', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)', icon: '🎙️' },
  translating: { label: '翻译中', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.15)', icon: '🌐' },
  translating_subtitle: { label: '翻译字幕', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.15)', icon: '💬' },
  generating_subtitles: { label: '生成字幕', color: '#e879f9', bg: 'rgba(232, 121, 249, 0.15)', icon: '📝' },
  burning_subtitles: { label: '压制字幕', color: '#f472b6', bg: 'rgba(244, 114, 182, 0.15)', icon: '🎬' },
  encoding_video: { label: '视频压制', color: '#f472b6', bg: 'rgba(244, 114, 182, 0.15)', icon: '⚙️' },
  tagging: { label: '生成标签', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)', icon: '🏷️' },
  partitioning: { label: '推荐分区', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)', icon: '📂' },
  moderating: { label: '审核中', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)', icon: '🛡️' },
  awaiting_manual_review: { label: '待人工审核', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)', icon: '👀' },
  awaiting_review: { label: '待人工审核', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)', icon: '👀' },
  ready_for_upload: { label: '等待上传', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)', icon: '🚀' },
  uploading: { label: '上传中', color: '#fb923c', bg: 'rgba(251, 146, 60, 0.15)', icon: '☁️' },
  completed: { label: '已完成', color: '#34d399', bg: 'rgba(52, 211, 153, 0.15)', icon: '✅' },
  failed: { label: '处理失败', color: '#f87171', bg: 'rgba(248, 113, 113, 0.15)', icon: '❌' },
  abandoned: { label: '已废弃', color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)', icon: '🗑️' },
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
  onNavigateCreateTask,
}) {
  const [deletingId, setDeletingId] = useState(null);
  const [isClearing, setIsClearing] = useState(false);

  const renderStatusBadge = (task) => {
    const s = STATUS_MAP[task.status] || {
      label: task.status || '未知',
      color: '#cbd5e1',
      bg: 'rgba(203, 213, 225, 0.15)',
      icon: '•',
    };

    const hasQcWarning = Boolean(task.subtitle_qc_failed || task.asr_warning_message || task.subtitle_warning_message);
    let warningTip = '';
    if (task.subtitle_qc_failed) warningTip += `字幕质检未通过: ${task.subtitle_qc_reason || '未知原因'}; `;
    if (task.asr_warning_message) warningTip += `ASR警告: ${task.asr_warning_message}; `;
    if (task.subtitle_warning_message) warningTip += `烧录警告: ${task.subtitle_warning_message}; `;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '3px', whiteSpace: 'nowrap' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            fontWeight: 600,
            color: s.color,
            backgroundColor: s.bg,
            border: `1px solid ${s.color}33`,
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          <span>{s.icon}</span>
          {s.label}
        </span>

        {task.upload_progress && ['uploading', 'downloading', 'asr_transcribing', 'translating_subtitle', 'encoding_video'].includes(task.status) && (
          <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginLeft: '4px', whiteSpace: 'nowrap' }}>
            {task.upload_progress}
          </span>
        )}

        {hasQcWarning && (
          <span
            className="badge"
            style={{
              background: 'rgba(245, 158, 11, 0.15)',
              color: '#fbbf24',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              fontSize: '0.68rem',
              padding: '1px 5px',
              cursor: 'help',
              whiteSpace: 'nowrap',
            }}
            title={warningTip.trim()}
          >
            ⚠️ 字幕异常
          </span>
        )}
      </div>
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

  const renderPartition = (task) => {
    const target = (task.upload_target || 'bilibili').toLowerCase();
    if (target === 'both') {
      const ac = task.partition_name_acfun || task.selected_partition_id_acfun || task.recommended_partition_id_acfun;
      const bili = task.partition_name_bilibili || task.selected_partition_id_bilibili || task.recommended_partition_id_bilibili;
      if (!ac && !bili) return <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>未设置</span>;
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', whiteSpace: 'nowrap' }}>
          {bili && (
            <span className="tag-pill" style={{ color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.25)' }}>
              B站: {bili}
            </span>
          )}
          {ac && (
            <span className="tag-pill" style={{ color: '#fd4c5a', borderColor: 'rgba(253, 76, 90, 0.25)' }}>
              A站: {ac}
            </span>
          )}
        </div>
      );
    }
    if (target === 'bilibili') {
      const bili = task.partition_name_bilibili || task.selected_partition_id_bilibili || task.recommended_partition_id_bilibili || task.selected_partition_id || task.recommended_partition_id;
      return bili ? (
        <span className="tag-pill" style={{ color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.25)', whiteSpace: 'nowrap' }}>
          {bili}
        </span>
      ) : (
        <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>未设置</span>
      );
    }
    const ac = task.partition_name_acfun || task.selected_partition_id_acfun || task.recommended_partition_id_acfun || task.selected_partition_id || task.recommended_partition_id;
    return ac ? (
      <span className="tag-pill" style={{ color: '#fd4c5a', borderColor: 'rgba(253, 76, 90, 0.25)', whiteSpace: 'nowrap' }}>
        {ac}
      </span>
    ) : (
      <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>未设置</span>
    );
  };

  const renderTags = (tagsRaw) => {
    if (!tagsRaw) return <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>未生成</span>;
    let tags = [];
    try {
      tags = typeof tagsRaw === 'string' ? JSON.parse(tagsRaw) : tagsRaw;
      if (!Array.isArray(tags)) tags = [];
    } catch {
      tags = [];
    }
    if (tags.length === 0) return <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>未生成</span>;

    const displayTags = tags.slice(0, 2);
    const remaining = tags.length - 2;

    return (
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'nowrap', alignItems: 'center' }} title={`完整标签: ${tags.join(', ')}`}>
        {displayTags.map((t, idx) => (
          <span key={idx} className="tag-pill" style={{ maxWidth: '72px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {t}
          </span>
        ))}
        {remaining > 0 && (
          <span className="tag-pill" style={{ background: 'rgba(255, 255, 255, 0.1)', color: 'var(--text-main)' }}>
            +{remaining}
          </span>
        )}
      </div>
    );
  };

  const renderUploadResult = (task) => {
    let biliRes = null;
    let acRes = null;

    if (task.bilibili_upload_response) {
      try {
        biliRes = typeof task.bilibili_upload_response === 'string'
          ? JSON.parse(task.bilibili_upload_response)
          : task.bilibili_upload_response;
      } catch {}
    }
    if (task.acfun_upload_response) {
      try {
        acRes = typeof task.acfun_upload_response === 'string'
          ? JSON.parse(task.acfun_upload_response)
          : task.acfun_upload_response;
      } catch {}
    }

    const results = [];
    if (biliRes?.bvid) {
      results.push(
        <a
          key="bili"
          href={biliRes.url || `https://www.bilibili.com/video/${biliRes.bvid}`}
          target="_blank"
          rel="noopener noreferrer"
          className="badge"
          style={{
            background: 'rgba(52, 211, 153, 0.15)',
            color: '#34d399',
            border: '1px solid rgba(52, 211, 153, 0.3)',
            textDecoration: 'none',
            fontSize: '0.72rem',
            padding: '2px 8px',
          }}
          title="点击在 B 站查看视频"
        >
          📺 {biliRes.bvid}
        </a>
      );
    }

    if (acRes?.ac_number) {
      results.push(
        <a
          key="ac"
          href={`https://www.acfun.cn/v/ac${acRes.ac_number}`}
          target="_blank"
          rel="noopener noreferrer"
          className="badge"
          style={{
            background: 'rgba(52, 211, 153, 0.15)',
            color: '#34d399',
            border: '1px solid rgba(52, 211, 153, 0.3)',
            textDecoration: 'none',
            fontSize: '0.72rem',
            padding: '2px 8px',
          }}
          title="点击在 AcFun 查看视频"
        >
          🍌 AC{acRes.ac_number}
        </a>
      );
    }

    if (results.length > 0) {
      return <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', whiteSpace: 'nowrap' }}>{results}</div>;
    }

    if (task.status === 'failed') {
      const errorMsg = task.error_message || '任务处理失败';
      return (
        <span
          className="badge"
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            cursor: 'pointer',
            maxWidth: '120px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontSize: '0.72rem',
            padding: '2px 8px',
          }}
          title={`点击查看错误: ${errorMsg}`}
          onClick={() => alert(`【任务失败详情】\n任务ID: ${task.id}\n错误原因:\n${errorMsg}`)}
        >
          ❌ 失败详情
        </span>
      );
    }

    if (task.status === 'uploading') {
      return (
        <span className="badge" style={{ background: 'rgba(251, 146, 60, 0.15)', color: '#fb923c', fontSize: '0.72rem' }}>
          ☁️ 上传中
        </span>
      );
    }

    return <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>待上传</span>;
  };

  const copyId = (id) => {
    navigator.clipboard?.writeText(id);
  };

  const formatDateTime = (timeStr) => {
    if (!timeStr) return '刚刚';
    return timeStr.replace('T', ' ').split('.')[0];
  };

  const handleDelete = async (task) => {
    const taskName = task.video_title_translated || task.video_title_original || task.video_title || task.id;
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
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
            }}>
              总计 {total}
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            通过 GET /api/tasks 实时获取
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {onNavigateCreateTask && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNavigateCreateTask}
              style={{ padding: '6px 14px', fontSize: '0.825rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              title="切换到新建任务面板"
            >
              <span>➕</span>
              <span>新建任务</span>
            </button>
          )}

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
          <div style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            点击“新建任务”输入 YouTube 链接添加您的第一个搬运任务吧
          </div>
          {onNavigateCreateTask && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNavigateCreateTask}
              style={{ marginTop: '16px', padding: '8px 18px', fontSize: '0.85rem' }}
            >
              ➕ 立即新建任务
            </button>
          )}
        </div>
      ) : (
        <div className="task-table-wrapper">
          <table className="task-table">
            <thead>
              <tr>
                <th style={{ width: '90px' }}>任务状态</th>
                <th style={{ width: '110px' }}>发布目标</th>
                <th style={{ minWidth: '220px' }}>视频源 / 标题</th>
                <th style={{ width: '95px' }}>分区</th>
                <th style={{ width: '115px' }}>标签</th>
                <th style={{ width: '115px' }}>上传结果</th>
                <th style={{ width: '125px' }}>创建时间</th>
                <th style={{ width: '110px', textAlign: 'right' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => {
                const mainTitle = task.video_title_translated || task.video_title_original || task.video_title || task.youtube_url;
                const originalTitle = task.video_title_original;
                const hasDifferentOriginal = task.video_title_translated && originalTitle && task.video_title_translated !== originalTitle;

                return (
                  <tr key={task.id}>
                    {/* 1. 任务状态 */}
                    <td>{renderStatusBadge(task)}</td>

                    {/* 2. 发布目标 & 合集 */}
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '4px', whiteSpace: 'nowrap' }}>
                        {getPlatformBadge(task.upload_target)}
                        {task.bilibili_season_title && (
                          <span
                            className="badge-season"
                            title={`B站合集: ${task.bilibili_season_title}`}
                          >
                            📚 {task.bilibili_season_title}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* 3. 视频源 / 标题 */}
                    <td>
                      <div>
                        <div
                          className="title-clamp-2"
                          style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '0.85rem' }}
                          title={mainTitle}
                        >
                          {mainTitle}
                        </div>
                        {hasDifferentOriginal && (
                          <div
                            style={{
                              fontSize: '0.72rem',
                              color: 'var(--text-dim)',
                              marginTop: '2px',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                            title={`原标题: ${originalTitle}`}
                          >
                            原: {originalTitle}
                          </div>
                        )}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                          <span
                            style={{
                              fontSize: '0.7rem',
                              color: 'var(--text-dim)',
                              fontFamily: 'var(--font-mono)',
                              cursor: 'pointer',
                              whiteSpace: 'nowrap',
                            }}
                            onClick={() => copyId(task.id)}
                            title="点击复制完整 ID"
                          >
                            ID: {task.id.slice(0, 8)}...
                          </span>
                          {task.youtube_url && (
                            <a
                              href={task.youtube_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                fontSize: '0.7rem',
                                color: '#38bdf8',
                                textDecoration: 'none',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '2px',
                                opacity: 0.85,
                                whiteSpace: 'nowrap',
                              }}
                              title="在 YouTube 打开原视频"
                            >
                              🔗 原片
                            </a>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* 4. 分区 */}
                    <td>{renderPartition(task)}</td>

                    {/* 5. 标签 */}
                    <td>{renderTags(task.tags_generated)}</td>

                    {/* 6. 上传结果 */}
                    <td>{renderUploadResult(task)}</td>

                    {/* 7. 创建时间 */}
                    <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                      {formatDateTime(task.created_at)}
                    </td>

                    {/* 8. 操作 */}
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', alignItems: 'center', whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => copyId(task.id)}
                          title="复制完整任务ID"
                          style={{ padding: '4px 8px', fontSize: '0.75rem', whiteSpace: 'nowrap' }}
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
                            whiteSpace: 'nowrap',
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
                );
              })}
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
