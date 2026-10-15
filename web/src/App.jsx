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
  const [taskPage, setTaskPage] = useState(1);
  const [taskPerPage, setTaskPerPage] = useState(20);
  const [totalTaskPages, setTotalTaskPages] = useState(1);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 避免轮询与异步回调闭包旧值
  const taskPageRef = React.useRef(taskPage);
  const taskPerPageRef = React.useRef(taskPerPage);

  useEffect(() => {
    taskPageRef.current = taskPage;
  }, [taskPage]);

  useEffect(() => {
    taskPerPageRef.current = taskPerPage;
  }, [taskPerPage]);

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
  const fetchTasks = useCallback(async (targetPage, targetPerPage, silent = false) => {
    const p = targetPage !== undefined ? targetPage : taskPageRef.current;
    const size = targetPerPage !== undefined ? targetPerPage : taskPerPageRef.current;
    if (!silent) setLoadingTasks(true);
    try {
      const data = await api.getTasks({ page: p, per_page: size });
      if (data.success) {
        setTasks(data.tasks || []);
        const total = data.total || 0;
        setTotalTasks(total);
        const pages = data.total_pages || Math.max(1, Math.ceil(total / size));
        setTotalTaskPages(pages);
        if (data.page && data.page !== p) {
          setTaskPage(data.page);
        }
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

  // 翻页与每页大小修改处理
  const handleTaskPageChange = (newPage) => {
    setTaskPage(newPage);
    fetchTasks(newPage, taskPerPageRef.current, false);
  };

  const handleTaskPerPageChange = (newSize) => {
    setTaskPerPage(newSize);
    setTaskPage(1);
    fetchTasks(1, newSize, false);
  };

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
        fetchTasks(1, taskPerPageRef.current);
        fetchMonitors();
      }
    });
  }, [checkAuth, fetchTasks, fetchMonitors]);

  // 轮询近期数据
  useEffect(() => {
    if (!authState.loggedIn) return;
    const timer = setInterval(() => {
      if (activeTab === 'tasks' || activeTab === 'create_task') {
        fetchTasks(taskPageRef.current, taskPerPageRef.current, true);
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
      fetchTasks(1, taskPerPageRef.current);
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
      setTaskPage(1);
      setTotalTaskPages(1);
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
      // 创建成功后自动切回第1页以便查看最新任务，并跳转到任务列表
      setTaskPage(1);
      fetchTasks(1, taskPerPageRef.current, true);
      setActiveTab('tasks');
    }
    return res;
  };

  // 删除单任务
  const handleDeleteTask = async (taskId) => {
    try {
      const res = await api.deleteTask(taskId, true);
      if (res.success) {
        showToast(res.message || '任务已成功删除', 'success');
        const currentPage = taskPageRef.current;
        const currentSize = taskPerPageRef.current;
        const targetPage = (tasks.length <= 1 && currentPage > 1) ? currentPage - 1 : currentPage;
        if (targetPage !== currentPage) {
          setTaskPage(targetPage);
        }
        fetchTasks(targetPage, currentSize, true);
      }
      return res;
    } catch (err) {
      showToast(err.message || '删除任务失败', 'error');
      throw err;
    }
  };

  // 清空所有任务
  const handleClearAllTasks = async () => {
    try {
      const res = await api.clearAllTasks(true);
      if (res.success) {
        showToast(res.message || '所有任务已成功清空', 'success');
        setTaskPage(1);
        setTotalTaskPages(1);
        fetchTasks(1, taskPerPageRef.current, false);
      }
      return res;
    } catch (err) {
      showToast(err.message || '清空任务失败', 'error');
      throw err;
    }
  };

  // 重新开始失败/待处理任务
  const handleRestartTask = async (taskId) => {
    try {
      const res = await api.restartTask(taskId);
      if (res.success) {
        showToast(res.message || '任务已重新启动', 'success');
        fetchTasks(taskPageRef.current, taskPerPageRef.current, true);
      }
      return res;
    } catch (err) {
      showToast(err.message || '重新开始任务失败', 'error');
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
          if (tab === 'tasks') fetchTasks(taskPageRef.current, taskPerPageRef.current);
          if (tab === 'playlist') fetchMonitors();
        }}
      />

      <main className="main-content">
        {requireLoginBlock ? (
          <div style={{ marginTop: '40px' }}>
            <LoginForm onLoginSuccess={handleLogin} />
          </div>
        ) : activeTab === 'tasks' ? (
          <TaskList
            tasks={tasks}
            total={totalTasks}
            page={taskPage}
            pageSize={taskPerPage}
            totalPages={totalTaskPages}
            loading={loadingTasks}
            onRefresh={() => fetchTasks(taskPage, taskPerPage, false)}
            onDelete={handleDeleteTask}
            onRestart={handleRestartTask}
            onClearAll={handleClearAllTasks}
            onPageChange={handleTaskPageChange}
            onPageSizeChange={handleTaskPerPageChange}
            onNavigateCreateTask={() => setActiveTab('create_task')}
          />
        ) : activeTab === 'create_task' ? (
          <div style={{ maxWidth: '640px', margin: '0 auto' }}>
            <CreateTaskCard
              onTaskCreated={handleTaskCreated}
              isSubmitting={isSubmitting}
              setIsSubmitting={setIsSubmitting}
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
