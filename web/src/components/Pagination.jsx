import React, { useState } from 'react';

/**
 * 通用分页组件
 * 
 * @param {number} currentPage 当前页码（从 1 开始）
 * @param {number} totalItems 总记录数
 * @param {number} pageSize 每页条数
 * @param {number} totalPages 总页数（可选）
 * @param {Function} onPageChange 页码改变回调
 * @param {Function} onPageSizeChange 每页大小改变回调
 * @param {boolean} loading 加载中状态
 * @param {number[]} pageSizeOptions 可选每页大小列表
 * @param {boolean} showQuickJumper 是否显示快速跳转
 * @param {boolean} showSizeChanger 是否显示每页条数选择
 */
export function Pagination({
  currentPage = 1,
  totalItems = 0,
  pageSize = 20,
  totalPages: propTotalPages,
  onPageChange,
  onPageSizeChange,
  loading = false,
  pageSizeOptions = [10, 20, 50, 100],
  showQuickJumper = true,
  showSizeChanger = true,
}) {
  const totalPages = propTotalPages !== undefined 
    ? Math.max(1, propTotalPages) 
    : Math.max(1, Math.ceil(totalItems / pageSize));

  const [jumpInput, setJumpInput] = useState('');

  if (totalItems <= 0) {
    return null;
  }

  // 计算显示的页码列表（带省略号）
  const getPageNumbers = () => {
    const pages = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // 总页数较多时的智能分页
      if (currentPage <= 4) {
        for (let i = 1; i <= 5; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 3) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 4; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        pages.push(1);
        pages.push('...');
        pages.push(currentPage - 1);
        pages.push(currentPage);
        pages.push(currentPage + 1);
        pages.push('...');
        pages.push(totalPages);
      }
    }
    return pages;
  };

  const handlePageClick = (page) => {
    if (page === currentPage || page < 1 || page > totalPages || loading) return;
    onPageChange?.(page);
  };

  const handleJumpSubmit = (e) => {
    e.preventDefault();
    const target = parseInt(jumpInput, 10);
    if (!isNaN(target) && target >= 1 && target <= totalPages) {
      if (target !== currentPage) {
        onPageChange?.(target);
      }
      setJumpInput('');
    }
  };

  // 当前显示条目范围计算
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className="pagination-container">
      {/* 统计信息与每页条数选择 */}
      <div className="pagination-info-wrapper">
        <span className="pagination-info-text">
          共 <strong className="highlight-number">{totalItems}</strong> 条任务
          <span className="pagination-range-text">
            （第 {startItem} - {endItem} 条）
          </span>
        </span>

        {showSizeChanger && onPageSizeChange && (
          <div className="pagination-size-selector">
            <select
              value={pageSize}
              disabled={loading}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="pagination-select"
              title="切换每页显示条数"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt} 条 / 页
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 页码与翻页按钮组 */}
      <div className="pagination-actions-wrapper">
        <div className="pagination-btn-group">
          {/* 首页 */}
          <button
            type="button"
            className="pagination-btn pagination-btn-nav"
            onClick={() => handlePageClick(1)}
            disabled={currentPage <= 1 || loading}
            title="第一页"
          >
            «
          </button>

          {/* 上一页 */}
          <button
            type="button"
            className="pagination-btn pagination-btn-nav"
            onClick={() => handlePageClick(currentPage - 1)}
            disabled={currentPage <= 1 || loading}
            title="上一页"
          >
            ‹
          </button>

          {/* 页码序列 */}
          {getPageNumbers().map((item, idx) => {
            if (item === '...') {
              return (
                <span key={`ellipsis-${idx}`} className="pagination-ellipsis">
                  •••
                </span>
              );
            }

            const isCurrent = item === currentPage;
            return (
              <button
                key={`page-${item}`}
                type="button"
                className={`pagination-btn ${isCurrent ? 'pagination-btn-active' : ''}`}
                onClick={() => handlePageClick(item)}
                disabled={loading}
              >
                {item}
              </button>
            );
          })}

          {/* 下一页 */}
          <button
            type="button"
            className="pagination-btn pagination-btn-nav"
            onClick={() => handlePageClick(currentPage + 1)}
            disabled={currentPage >= totalPages || loading}
            title="下一页"
          >
            ›
          </button>

          {/* 末页 */}
          <button
            type="button"
            className="pagination-btn pagination-btn-nav"
            onClick={() => handlePageClick(totalPages)}
            disabled={currentPage >= totalPages || loading}
            title="最后一页"
          >
            »
          </button>
        </div>

        {/* 快速跳页 */}
        {showQuickJumper && totalPages > 1 && (
          <form onSubmit={handleJumpSubmit} className="pagination-quick-jump">
            <span className="pagination-jump-label">跳至</span>
            <input
              type="number"
              min="1"
              max={totalPages}
              value={jumpInput}
              disabled={loading}
              onChange={(e) => setJumpInput(e.target.value)}
              placeholder={String(currentPage)}
              className="pagination-jump-input"
            />
            <span className="pagination-jump-label">页</span>
            <button
              type="submit"
              disabled={loading || !jumpInput}
              className="pagination-jump-btn"
            >
              确定
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
