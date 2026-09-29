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
  async createTask({ youtube_url, upload_target = 'acfun', auto_start = true }) {
    return request('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        youtube_url,
        upload_target,
        auto_start,
      }),
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
};
