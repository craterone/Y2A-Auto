# Y2A-Auto Web 客户端 (React + Vite)

本目录为 Y2A-Auto 的现代化 React 前端，通过调用后端的 RESTful API (`api.py`) 实现系统认证与任务管理。

## 技术栈与设计

- **框架**：React 19 + Vite 6
- **样式**：Vanilla CSS（深色毛玻璃现代拟态 Glassmorphism 设计系统）
- **字体**：Inter + JetBrains Mono
- **接口集成**：RESTful API（支持自动 Session Cookie 状态维护）

## 功能特性

1. **系统身份验证**
   - 自动检测后端密码保护状态 (`GET /api/auth/status`)
   - 登录凭据校验 (`POST /api/login`)，支持防爆破锁定倒计时与错误次数提示
   - 一键安全注销 (`POST /api/logout`)
2. **新建搬运任务**
   - YouTube 视频或播放列表链接录入 (`POST /api/tasks`)
   - 智能识别播放列表并支持批量创建
   - 支持发布目标选择：AcFun (A站)、Bilibili (B站)、双平台同步
   - 支持“创建后立即启动处理”开关
3. **实时任务监控**
   - 实时拉取最新任务队列与状态 (`GET /api/tasks`)
   - 多彩状态指示（排队中、下载中、语音识别、翻译中、已完成、失败等）
   - 一键复制任务 UUID

## 运行方式

### 1. 安装依赖（已安装）
```bash
npm install
```

### 2. 启动开发服务器
开发服务器已配置反向代理至后端 `http://127.0.0.1:5002`：
```bash
npm run dev
```
启动后访问 `http://localhost:3000` 即可开始使用。

### 3. 生产打包
```bash
npm run build
```
打包文件将输出至 `dist/` 目录。
