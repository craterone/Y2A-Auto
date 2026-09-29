import React, { useState, useEffect, useCallback } from 'react';
import { api } from './api';
import { Navbar } from './components/Navbar';
import { LoginForm } from './components/LoginForm';
import { CreateTaskCard } from './components/CreateTaskCard';
import { TaskList } from './components/TaskList';
import { Toast } from './components/Toast';

export function App() {
  const [authState, setAuthState] = useState({
    loggedIn: false,
    passwordProtectionEnabled: false,
    checked: false,
  });

  const [showLoginModal, setShowLoginModal] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [totalTasks, setTotalTasks] = useState(0);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
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

  // 初始化
  useEffect(() => {
    checkAuth().then((auth) => {
      if (auth && auth.logged_in) {
        fetchTasks();
      }
    });
  }, [checkAuth, fetchTasks]);

  // 轮询近期任务状态
  useEffect(() => {
    if (!authState.loggedIn) return;
    const timer = setInterval(() => {
      fetchTasks(true);
    }, 8000);
    return () => clearInterval(timer);
  }, [authState.loggedIn, fetchTasks]);

  // 登录动作
  const handleLogin = async (password) => {
    const res = await api.login(password);
    if (res.success) {
      setAuthState((prev) => ({ ...prev, loggedIn: true }));
      setShowLoginModal(false);
      showToast('登录成功，欢迎使用 Y2A-Auto！', 'success');
      fetchTasks();
    }
  };

  // 退出登录
  const handleLogout = async () => {
    try {
      await api.logout();
      setAuthState((prev) => ({ ...prev, loggedIn: false }));
      setTasks([]);
      setTotalTasks(0);
      showToast('已安全退出登录', 'info');
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // 创建任务
  const handleTaskCreated = async (taskPayload) => {
    const res = await api.createTask(taskPayload);
    if (res.success) {
      showToast(res.message || '任务创建成功！', 'success');
      fetchTasks(true);
    }
    return res;
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
      />

      <main className="main-content">
        {requireLoginBlock ? (
          <div style={{ marginTop: '40px' }}>
            <LoginForm onLoginSuccess={handleLogin} />
          </div>
        ) : (
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
            />
          </div>
        )}
      </main>

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
