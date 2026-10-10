import React, { useState, useEffect, useCallback } from 'react';
import { api } from './api';
import { Navbar } from './components/Navbar';
import { LoginForm } from './components/LoginForm';
import { CreateTaskCard } from './components/CreateTaskCard';
import { TaskList } from './components/TaskList';
import { PlaylistMonitorCard } from './components/PlaylistMonitorCard';
import { PlaylistMonitorList } from './components/PlaylistMonitorList';
import { PlaylistTasksModal } from './components/PlaylistTasksModal';
import { Toast } from './components/Toast';

export function App() {
  const [authState, setAuthState] = useState({
    loggedIn: false,
    passwordProtectionEnabled: false,
    checked: false,
  });

  const [activeTab, setActiveTab] = useState('tasks'); // 'tasks' | 'playlist'
  const [showLoginModal, setShowLoginModal] = useState(false);
  
  // 单视频任务状态
  const [tasks, setTasks] = useState([]);
  const [totalTasks, setTotalTasks] = useState(0);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Playlist 监控状态
  const [monitors, setMonitors] = useState([]);
  const [loadingMonitors, setLoadingMonitors] = useState(false);
  const [activePlaylistForTasks, setActivePlaylistForTasks] = useState(null);

  const [toasts, setToasts] = useState([]);

  // Toast 调度
  const showToast = useCallback((message, type = 'info', duration = 3500) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    }
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // 检查认证状态
  const checkAuth = useCallback(async () => {
    try {
      const data = await api.getAuthStatus();
      setAuthState({
        loggedIn: data.logged_in,
        passwordProtectionEnabled: data.password_protection_enabled,
        checked: true,
      });
      return data;
    } catch (err) {
      setAuthState((prev) => ({ ...prev, checked: true }));
      showToast(err.message, 'error');
      return null;
    }
  }, [showToast]);

  // 拉取任务列表
  const fetchTasks = useCallback(async (silent = false) => {
    if (!silent) setLoadingTasks(true);
    try {
      const data = await api.getTasks({ page: 1, per_page: 20 });
      if (data.success) {
        setTasks(data.tasks || []);
        setTotalTasks(data.total || 0);
      }
    } catch (err) {
      if (err.status === 401) {
        setAuthState((prev) => ({ ...prev, loggedIn: false }));
      } else if (!silent) {
        showToast(err.message, 'error');
      }
    } finally {
      if (!silent) setLoadingTasks(false);
    }
  }, [showToast]);

  // 拉取 Playlist 监控配置列表
  const fetchMonitors = useCallback(async (silent = false) => {
    if (!silent) setLoadingMonitors(true);
    try {
      const data = await api.getPlaylistMonitors();
      if (data.success) {
        setMonitors(data.monitors || []);
      }
    } catch (err) {
      if (err.status === 401) {
        setAuthState((prev) => ({ ...prev, loggedIn: false }));
      } else if (!silent) {
        showToast(err.message, 'error');
      }
    } finally {
      if (!silent) setLoadingMonitors(false);
    }
  }, [showToast]);

  // 初始化
  useEffect(() => {
    checkAuth().then((auth) => {
      if (auth && auth.logged_in) {
        fetchTasks();
        fetchMonitors();
      }
    });
  }, [checkAuth, fetchTasks, fetchMonitors]);

  // 轮询近期数据
  useEffect(() => {
    if (!authState.loggedIn) return;
    const timer = setInterval(() => {
      if (activeTab === 'tasks') {
        fetchTasks(true);
      } else if (activeTab === 'playlist') {
        fetchMonitors(true);
      }
    }, 8000);
    return () => clearInterval(timer);
  }, [authState.loggedIn, activeTab, fetchTasks, fetchMonitors]);

  // 登录动作
  const handleLogin = async (password) => {
    const res = await api.login(password);
    if (res.success) {
      setAuthState((prev) => ({ ...prev, loggedIn: true }));
      setShowLoginModal(false);
      showToast('登录成功，欢迎使用 Y2A-Auto！', 'success');
      fetchTasks();
      fetchMonitors();
    }
  };

  // 退出登录
  const handleLogout = async () => {
    try {
      await api.logout();
      setAuthState((prev) => ({ ...prev, loggedIn: false }));
      setTasks([]);
      setTotalTasks(0);
      setMonitors([]);
      showToast('已安全退出登录', 'info');
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // 创建单任务
  const handleTaskCreated = async (taskPayload) => {
    const res = await api.createTask(taskPayload);
    if (res.success) {
      showToast(res.message || '任务创建成功！', 'success');
      fetchTasks(true);
    }
    return res;
  };

  // 删除单任务
  const handleDeleteTask = async (taskId) => {
    try {
      const res = await api.deleteTask(taskId, true);
      if (res.success) {
        showToast(res.message || '任务已成功删除', 'success');
        fetchTasks(true);
      }
      return res;
    } catch (err) {
      showToast(err.message || '删除任务失败', 'error');
      throw err;
    }
  };

  // 新建 Playlist 监控回调
  const handleMonitorCreated = () => {
    fetchMonitors(false);
  };


  // 首屏加载中
  if (!authState.checked) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '16px',
        color: 'var(--text-dim)',
      }}>
        <div className="spinner" style={{ width: '32px', height: '32px' }} />
        <span style={{ fontSize: '0.9rem' }}>正在连接 Y2A-Auto 系统...</span>
      </div>
    );
  }

  // 若开启密码保护且未登录，直接显示全屏登录面板
  const requireLoginBlock = authState.passwordProtectionEnabled && !authState.loggedIn;

  return (
    <div className="app-container">
      <Navbar
        authState={authState}
        onLogout={handleLogout}
        onOpenLogin={() => setShowLoginModal(true)}
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          if (tab === 'tasks') fetchTasks();
          if (tab === 'playlist') fetchMonitors();
        }}
      />

      <main className="main-content">
        {requireLoginBlock ? (
          <div style={{ marginTop: '40px' }}>
            <LoginForm onLoginSuccess={handleLogin} />
          </div>
        ) : activeTab === 'tasks' ? (
          <div className="grid-layout">
            <CreateTaskCard
              onTaskCreated={handleTaskCreated}
              isSubmitting={isSubmitting}
              setIsSubmitting={setIsSubmitting}
            />
            <TaskList
              tasks={tasks}
              total={totalTasks}
              loading={loadingTasks}
              onRefresh={() => fetchTasks(false)}
              onDelete={handleDeleteTask}
            />

          </div>
        ) : (
          <div style={{ maxWidth: '1080px', margin: '0 auto' }}>
            <PlaylistMonitorCard
              onMonitorCreated={handleMonitorCreated}
              showToast={showToast}
            />
            <PlaylistMonitorList
              monitors={monitors}
              isLoading={loadingMonitors}
              onRefresh={() => fetchMonitors(false)}
              onViewTasks={(m) => setActivePlaylistForTasks(m)}
              showToast={showToast}
            />
          </div>
        )}
      </main>

      {/* 查看该 Playlist 所有 Task 的模态框（支持时间倒序或顺序查看） */}
      {activePlaylistForTasks && (
        <PlaylistTasksModal
          monitor={activePlaylistForTasks}
          onClose={() => setActivePlaylistForTasks(null)}
          showToast={showToast}
        />
      )}

      {/* 模态框登录 */}
      {showLoginModal && (
        <LoginForm
          isModal
          onLoginSuccess={handleLogin}
          onClose={() => setShowLoginModal(false)}
        />
      )}

      {/* 提示层 */}
      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default App;
