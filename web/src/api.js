/**
 * Y2A-Auto RESTful API 客户端
 */

const API_BASE = '/api';

/**
 * 通用 fetch 包装函数
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
    credentials: 'include', // 携带 session cookie
  };

  try {
    const response = await fetch(url, config);
    let data;
    try {
      data = await response.json();
    } catch {
      data = { success: response.ok, message: response.statusText };
    }

    if (!response.ok) {
      const error = new Error(data.message || `请求失败 (${response.status})`);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (err) {
    if (err.status) {
      throw err;
    }
    const networkError = new Error('无法连接到后端服务，请检查网络或后端是否运行');
    networkError.status = 0;
    throw networkError;
  }
}

export const api = {
  /**
   * 用户登录
   */
  async login(password) {
    return request('/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
  },

  /**
   * 退出登录
   */
  async logout() {
    return request('/logout', {
      method: 'POST',
    });
  },

  /**
   * 获取当前认证状态
   */
  async getAuthStatus() {
    return request('/auth/status', {
      method: 'GET',
    });
  },

  /**
   * 添加新任务（单个视频或播放列表）
   */
  async createTask({
    youtube_url,
    upload_target = 'acfun',
    auto_start = true,
    bilibili_season_id,
    bilibili_section_id,
    bilibili_season_title,
  }) {
    const payload = {
      youtube_url,
      upload_target,
      auto_start,
    };
    if (bilibili_season_id) payload.bilibili_season_id = bilibili_season_id;
    if (bilibili_section_id) payload.bilibili_section_id = bilibili_section_id;
    if (bilibili_season_title) payload.bilibili_season_title = bilibili_season_title;

    return request('/tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * 分页获取任务列表
   */
  async getTasks({ page = 1, per_page = 15 } = {}) {
    return request(`/tasks?page=${page}&per_page=${per_page}`, {
      method: 'GET',
    });
  },

  /**
   * 获取单个任务详情
   */
  async getTask(taskId) {
    return request(`/tasks/${taskId}`, {
      method: 'GET',
    });
  },

  /**
   * 删除任务
   * @param {string} taskId 任务ID
   * @param {boolean} deleteFiles 是否同时清理关联文件，默认 true
   */
  async deleteTask(taskId, deleteFiles = true) {
    return request(`/tasks/${taskId}?delete_files=${deleteFiles}`, {
      method: 'DELETE',
    });
  },

  /**
   * 清空所有任务
   * @param {boolean} deleteFiles 是否同时清理关联文件，默认 true
   */
  async clearAllTasks(deleteFiles = true) {
    return request(`/tasks?delete_files=${deleteFiles}`, {
      method: 'DELETE',
    });
  },

  /**
   * 手动启动/重新开始任务（失败任务重启不受风控间隔限制）
   * @param {string} taskId 任务ID
   */
  async restartTask(taskId) {
    return request(`/tasks/${taskId}/start`, {
      method: 'POST',
    });
  },

  // ==========================================


  // Playlist 监控相关 API
  // ==========================================

  /**
   * 获取所有 Playlist 监控配置列表
   */
  async getPlaylistMonitors() {
    return request('/playlist-monitors', {
      method: 'GET',
    });
  },

  /**
   * 获取单个 Playlist 监控配置详情
   */
  async getPlaylistMonitor(monitorId) {
    return request(`/playlist-monitors/${monitorId}`, {
      method: 'GET',
    });
  },

  /**
   * 创建 Playlist 监控
   */
  async createPlaylistMonitor(payload) {
    return request('/playlist-monitors', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * 更新 Playlist 监控配置
   */
  async updatePlaylistMonitor(monitorId, payload) {
    return request(`/playlist-monitors/${monitorId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  /**
   * 删除 Playlist 监控配置
   */
  async deletePlaylistMonitor(monitorId, deleteTasks = false) {
    return request(`/playlist-monitors/${monitorId}?delete_tasks=${deleteTasks}`, {
      method: 'DELETE',
    });
  },

  /**
   * 立即触发一次检测
   */
  async checkPlaylistMonitorNow(monitorId) {
    return request(`/playlist-monitors/${monitorId}/check`, {
      method: 'POST',
    });
  },

  /**
   * 查看该 Playlist 下的所有 Task 列表
   * @param {number} monitorId 监控ID
   * @param {Object} options { order: 'desc' | 'asc', page, per_page, status }
   */
  async getPlaylistTasks(monitorId, { order = 'desc', page = 1, per_page = 20, status = '' } = {}) {
    const params = new URLSearchParams();
    if (order) params.set('order', order);
    if (page) params.set('page', page);
    if (per_page) params.set('per_page', per_page);
    if (status) params.set('status', status);

    return request(`/playlist-monitors/${monitorId}/tasks?${params.toString()}`, {
      method: 'GET',
    });
  },

  /**
   * 预览 YouTube Playlist 信息
   */
  async previewPlaylist(playlist_id) {
    return request('/playlist-monitors/preview', {
      method: 'POST',
      body: JSON.stringify({ playlist_id }),
    });
  },

  /**
   * 获取当前用户已创建的 Bilibili 合集列表（内置前端内存缓存与并发去重）
   * @param {boolean} refresh 是否强制跳过缓存刷新
   */
  async getBilibiliSeasons(refresh = false) {
    if (!refresh && window._bilibiliSeasonsCache) {
      return window._bilibiliSeasonsCache;
    }
    if (window._bilibiliSeasonsPromise) {
      return window._bilibiliSeasonsPromise;
    }
    const query = refresh ? '?refresh=true' : '';
    window._bilibiliSeasonsPromise = request(`/bilibili/seasons${query}`, {
      method: 'GET',
    })
      .then((res) => {
        if (res && res.success) {
          window._bilibiliSeasonsCache = res;
        }
        window._bilibiliSeasonsPromise = null;
        return res;
      })
      .catch((err) => {
        window._bilibiliSeasonsPromise = null;
        throw err;
      });

    return window._bilibiliSeasonsPromise;
  },
};


