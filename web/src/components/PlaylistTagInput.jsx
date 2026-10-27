import React, { useState, useEffect, useRef, useCallback } from 'react';

const DEFAULT_RECOMMENDED_TAGS = ['英语', '英语学习', '英语精听', '英语听力'];
const DEFAULT_STORAGE_KEY = 'y2a_cached_playlist_tags';

/**
 * PlaylistTagInput
 * 播放列表标签输入组件：
 * 1. 支持输入一个 tag 后按 Enter 立即添加并继续输入下一个；
 * 2. 添加后的 tag 自动在前端 localStorage 缓存，显示在下方，支持直接点击快速添加/取消；
 * 3. 完美兼容中文输入法（IME），避免输入拼音选词时误触发回车。
 */
export function PlaylistTagInput({
  tags = [],
  onChange,
  maxTags = 10,
  maxTagLength = 20,
  storageKey = DEFAULT_STORAGE_KEY,
  disabled = false,
}) {
  const [inputValue, setInputValue] = useState('');
  const [cachedTags, setCachedTags] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.filter((t) => typeof t === 'string' && t.trim());
        }
      }
    } catch {
      // 容错忽略
    }
    return DEFAULT_RECOMMENDED_TAGS;
  });
  const [isComposing, setIsComposing] = useState(false);
  const [errorNotice, setErrorNotice] = useState('');
  const inputRef = useRef(null);
  const noticeTimerRef = useRef(null);

  // 显示简短轻量提示
  const showNotice = useCallback((msg) => {
    setErrorNotice(msg);
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = setTimeout(() => {
      setErrorNotice('');
    }, 2500);
  }, []);

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    };
  }, []);

  // 将标签保存到 localStorage 缓存（置顶去重，最多存 30 个）
  const updateCacheWithTags = useCallback((newTagsToCache) => {
    if (!newTagsToCache || newTagsToCache.length === 0) return;
    setCachedTags((prev) => {
      const current = Array.isArray(prev) ? [...prev] : [];
      const newItems = newTagsToCache.filter(Boolean);
      const combined = [...newItems, ...current];
      
      const seen = new Set();
      const unique = [];
      for (const item of combined) {
        const trimmed = String(item).trim();
        if (!trimmed) continue;
        const lower = trimmed.toLowerCase();
        if (!seen.has(lower)) {
          seen.add(lower);
          unique.push(trimmed);
        }
        if (unique.length >= 30) break;
      }

      try {
        localStorage.setItem(storageKey, JSON.stringify(unique));
      } catch {
        // localStorage 满等情况忽略
      }
      return unique;
    });
  }, [storageKey]);

  // 清空历史缓存
  const handleClearCache = () => {
    if (window.confirm('确定要清空已缓存的常用/历史标签吗？')) {
      try {
        localStorage.removeItem(storageKey);
      } catch {
        // 忽略
      }
      setCachedTags([]);
      showNotice('已清空标签缓存');
    }
  };

  // 批量/单个添加标签
  const handleAddTag = (rawText) => {
    const textToAdd = (rawText !== undefined ? rawText : inputValue).trim();
    if (!textToAdd) return;

    if (tags.length >= maxTags) {
      showNotice(`已达到最大标签上限（最多 ${maxTags} 个）`);
      return;
    }

    // 支持逗号、分号或换行批量拆分
    const candidates = textToAdd
      .split(/[,，;；\n]+/)
      .map((t) => t.trim())
      .filter(Boolean);

    if (candidates.length === 0) return;

    const currentLowerSet = new Set(tags.map((t) => t.toLowerCase()));
    const validToAdd = [];

    for (let c of candidates) {
      if (c.length > maxTagLength) {
        c = c.slice(0, maxTagLength);
      }
      const lower = c.toLowerCase();
      if (currentLowerSet.has(lower)) {
        showNotice(`标签「${c}」已存在，已自动忽略`);
        continue;
      }
      if (tags.length + validToAdd.length >= maxTags) {
        showNotice(`已达到标签上限（最多 ${maxTags} 个）`);
        break;
      }
      validToAdd.push(c);
      currentLowerSet.add(lower);
    }

    if (validToAdd.length > 0) {
      const nextTags = [...tags, ...validToAdd];
      onChange?.(nextTags);
      updateCacheWithTags(validToAdd);
      setInputValue('');
    } else {
      setInputValue('');
    }

    // 保持输入焦点
    inputRef.current?.focus();
  };

  // 键盘事件处理：回车添加下一个
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      // 阻止外层表单提交
      e.preventDefault();
      // 中文拼音输入中选词时不触发添加
      if (isComposing) return;
      handleAddTag();
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      // 当输入框为空时按退格键删除最后一个标签
      handleRemoveTag(tags.length - 1);
    }
  };

  // 删除已添加的标签
  const handleRemoveTag = (indexToRemove) => {
    const nextTags = tags.filter((_, idx) => idx !== indexToRemove);
    onChange?.(nextTags);
  };

  // 点击下方缓存标签切换添加/移除
  const handleToggleCachedTag = (cachedTag) => {
    if (disabled) return;
    const exists = tags.some((t) => t.toLowerCase() === cachedTag.toLowerCase());
    if (exists) {
      // 如果已选中，点击取消该标签
      const nextTags = tags.filter((t) => t.toLowerCase() !== cachedTag.toLowerCase());
      onChange?.(nextTags);
    } else {
      // 如果未选中，点击添加
      handleAddTag(cachedTag);
    }
  };

  return (
    <div className="playlist-tag-input-container" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {/* 提示条 */}
      {errorNotice && (
        <div style={{
          fontSize: '0.75rem',
          color: '#facc15',
          background: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.25)',
          padding: '4px 10px',
          borderRadius: '6px',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <span>⚠️</span>
          <span>{errorNotice}</span>
        </div>
      )}

      {/* 已选标签列表与输入区域 */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: '8px',
          padding: '8px 10px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '8px',
          minHeight: '44px',
          transition: 'border-color 0.2s ease',
        }}
        onClick={() => inputRef.current?.focus()}
      >
        {/* 已选标签 chips */}
        {tags.map((tag, idx) => (
          <span
            key={`${tag}-${idx}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 9px',
              borderRadius: '9999px',
              background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.18) 0%, rgba(99, 102, 241, 0.22) 100%)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              color: '#38bdf8',
              fontSize: '0.8rem',
              fontWeight: 500,
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
              userSelect: 'none',
            }}
          >
            <span>🏷️ {tag}</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleRemoveTag(idx);
              }}
              disabled={disabled}
              title="删除标签"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'rgba(255, 255, 255, 0.6)',
                cursor: disabled ? 'not-allowed' : 'pointer',
                padding: '0 2px',
                fontSize: '0.85rem',
                lineHeight: 1,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '50%',
                transition: 'color 0.15s ease, transform 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#ef4444';
                e.currentTarget.style.transform = 'scale(1.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'rgba(255, 255, 255, 0.6)';
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              ×
            </button>
          </span>
        ))}

        {/* 输入框 */}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          disabled={disabled || tags.length >= maxTags}
          placeholder={
            tags.length >= maxTags
              ? `已满 ${maxTags} 个标签`
              : tags.length === 0
              ? '输入标签，按回车 Enter 添加下一个 (例如: 科技, 数码)'
              : '输入下一个标签，按回车 Enter 添加...'
          }
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          style={{
            flex: 1,
            minWidth: '220px',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-main, #f8fafc)',
            fontSize: '0.84rem',
            padding: '4px 6px',
          }}
        />

        {/* 快捷添加按钮（在输入有内容时显示） */}
        {inputValue.trim() && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={(e) => {
              e.stopPropagation();
              handleAddTag();
            }}
            disabled={disabled}
            style={{
              padding: '2px 10px',
              fontSize: '0.75rem',
              height: '26px',
              whiteSpace: 'nowrap',
              borderRadius: '6px',
            }}
          >
            + 添加
          </button>
        )}
      </div>

      {/* 说明文案与限制提示 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
        <span>
          按 <strong>Enter 回车</strong> 连续添加 · 单标签最多 {maxTagLength} 字 · 最多 {maxTags} 个标签
        </span>
        <span>
          已添加: <strong style={{ color: tags.length > 0 ? '#38bdf8' : 'inherit' }}>{tags.length}</strong> / {maxTags}
        </span>
      </div>

      {/* 下方：前端缓存标签池（点击直接添加） */}
      <div
        style={{
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px dashed rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          padding: '10px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            <span>💡</span>
            <span style={{ fontWeight: 500 }}>已缓存常用 / 历史标签（点击直接添加）：</span>
          </div>

          {cachedTags.length > 0 && (
            <button
              type="button"
              onClick={handleClearCache}
              disabled={disabled}
              title="清空常用标签历史记录"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-dim)',
                fontSize: '0.7rem',
                cursor: 'pointer',
                padding: '2px 6px',
                borderRadius: '4px',
                transition: 'color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-dim)')}
            >
              🗑️ 清空历史
            </button>
          )}
        </div>

        {cachedTags.length === 0 ? (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontStyle: 'italic', padding: '4px 0' }}>
            暂无缓存标签，在上方输入标签并按回车后将自动在此缓存，后续可一键快速添加
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
            {cachedTags.map((cachedTag) => {
              const isSelected = tags.some((t) => t.toLowerCase() === cachedTag.toLowerCase());
              return (
                <button
                  key={cachedTag}
                  type="button"
                  onClick={() => handleToggleCachedTag(cachedTag)}
                  disabled={disabled}
                  title={isSelected ? `已选中「${cachedTag}」，点击可移除` : `点击将「${cachedTag}」加入当前标签`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    transition: 'all 0.15s ease',
                    border: isSelected
                      ? '1px solid rgba(56, 189, 248, 0.45)'
                      : '1px solid rgba(255, 255, 255, 0.08)',
                    background: isSelected
                      ? 'rgba(56, 189, 248, 0.15)'
                      : 'rgba(255, 255, 255, 0.04)',
                    color: isSelected ? '#38bdf8' : 'var(--text-muted, #94a3b8)',
                    transform: 'none',
                    userSelect: 'none',
                  }}
                  onMouseEnter={(e) => {
                    if (!disabled) {
                      e.currentTarget.style.borderColor = isSelected ? '#ef4444' : 'rgba(168, 85, 247, 0.6)';
                      e.currentTarget.style.color = isSelected ? '#f87171' : '#c084fc';
                      e.currentTarget.style.background = isSelected ? 'rgba(239, 68, 68, 0.15)' : 'rgba(168, 85, 247, 0.12)';
                      e.currentTarget.style.transform = 'translateY(-1px)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!disabled) {
                      e.currentTarget.style.borderColor = isSelected
                        ? 'rgba(56, 189, 248, 0.45)'
                        : 'rgba(255, 255, 255, 0.08)';
                      e.currentTarget.style.color = isSelected ? '#38bdf8' : 'var(--text-muted, #94a3b8)';
                      e.currentTarget.style.background = isSelected
                        ? 'rgba(56, 189, 248, 0.15)'
                        : 'rgba(255, 255, 255, 0.04)';
                      e.currentTarget.style.transform = 'none';
                    }
                  }}
                >
                  <span>{isSelected ? '✓' : '+'}</span>
                  <span>{cachedTag}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
