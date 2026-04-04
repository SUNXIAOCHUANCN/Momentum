# 📚 新手指南：项目安装与配置

这是一个适合新手、步骤详细的 README.md 模板。你可以直接复制使用：

# 🎯 项目名称

> Momentum: 一个全栈移动端 Web 应用

## 📋 目录

- [前置要求](#前置要求)
- [安装步骤](#安装步骤)
  - [1. 安装 Git](#1-安装-git)
  - [2. 安装 Python](#2-安装-python)
  - [3. 安装 Node.js](#3-安装-nodejs)
  - [4. 克隆项目](#4-克隆项目)
- [配置环境](#配置环境)
  - [后端配置](#后端配置)
  - [前端配置](#前端配置)
- [启动项目](#启动项目)
- [常见问题](#常见问题)

---

## 📦 前置要求

在开始之前，请确保你的电脑满足以下条件：

- ✅ 操作系统：Windows 10/11、macOS 或 Linux
- ✅ 网络连接（用于下载依赖）
- ✅ 管理员权限（安装软件时需要）

---

## 🛠️ 安装步骤

### 1. 安装 Git

**Windows 用户：**
1. 访问 [Git 官网](https://git-scm.com/download/win)
2. 下载并安装 Git
3. 安装时保持默认设置即可
4. 验证安装：打开命令提示符（cmd），输入：
   ```bash
   git --version
   ```

**macOS 用户：**
```bash
# 如果已安装 Homebrew
brew install git

# 或直接使用 Xcode 命令行工具
xcode-select --install
```

**验证安装：**
```bash
git --version
```
如果显示版本号（如 `git version 2.xx.x`），说明安装成功。

---

### 2. 安装 Python

**步骤：**
1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载 Python 3.8 或更高版本（推荐最新稳定版）
3. **Windows 用户注意：** 安装时务必勾选 ✅ **"Add Python to PATH"**
4. 安装完成后，打开命令提示符，输入：
   ```bash
   python --version
   # 或
   python3 --version
   ```

**验证安装：**
```bash
python --version
```
应显示类似 `Python 3.10.0`
建议安装 `Python 3.11.5`

---

### 3. 安装 Node.js

**步骤：**
1. 访问 [Node.js 官网](https://nodejs.org/)
2. 下载 **LTS 版本**（长期支持版，推荐）
3. 双击安装包，保持默认设置安装
4. 安装完成后，打开命令提示符，输入：
   ```bash
   node --version
   npm --version
   ```

**验证安装：**
```bash
node -v    # 应显示 v16.x.x 或更高
npm -v     # 应显示 8.x.x 或更高
```

---

### 4. 克隆项目

**步骤：**
1. 选择一个合适的位置存放项目（如桌面或文档文件夹）
2. 打开命令提示符（Windows）或终端（macOS/Linux）
3. 进入你想存放项目的目录：
   ```bash
   # Windows 示例
   cd Desktop
   
   # macOS/Linux 示例
   cd ~/Documents
   ```

4. 克隆项目：
   ```bash
   git clone https://github.com/你的用户名/你的仓库名.git
   ```

5. 进入项目目录：
   ```bash
   cd 你的仓库名
   ```

---

## ⚙️ 配置环境

### 后端配置（Python）

**步骤：**

1. **进入后端目录：**
   ```bash
   cd backend
   ```

2. **创建虚拟环境：**
   
   **Windows：**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
   
   **macOS/Linux：**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   
   ✅ 激活成功后，命令行前面会出现 `(.venv)` 标识

3. **安装依赖：**
   ```bash
   # 如果有 requirements.txt 文件
   pip install -r requirements.txt
   
   # 如果没有，安装项目所需的包（示例）
   pip install flask
   # 或
   pip install fastapi uvicorn
   ```

4. **创建环境变量文件（如果需要）：**
   ```bash
   # 复制示例文件
   copy .env.example .env        # Windows
   cp .env.example .env          # macOS/Linux
   
   # 然后用文本编辑器打开 .env 文件，填入你的配置
   ```

5. **验证后端配置：**
   ```bash
   # 查看已安装的包
   pip list
   ```

---

### 前端配置（Node.js）

**新开一个命令提示符/终端窗口**（不要关闭后端窗口）

**步骤：**

1. **进入前端目录：**
   ```bash
   # 先回到项目根目录
   cd ..
   
   # 进入前端目录
   cd frontend
   ```

2. **安装依赖：**
   ```bash
   npm install
   ```
   
   或使用更快的镜像源（中国用户推荐）：
   ```bash
   npm config set registry https://registry.npmmirror.com
   npm install
   ```

3. **创建环境变量文件（如果需要）：**
   ```bash
   copy .env.example .env        # Windows
   cp .env.example .env          # macOS/Linux
   ```

4. **验证前端配置：**
   ```bash
   # 查看 package.json 中的脚本命令
   npm run
   ```

---

## 🚀 启动项目

### 启动后端

**在第一个终端窗口（backend 目录）：**

```bash
# 确保虚拟环境已激活（命令行前有 .venv 标识）
# 如果没有，重新激活：
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 启动后端服务（根据实际项目调整）
python main.py

# 或使用 Flask
# flask run

# 或使用 FastAPI
# uvicorn main:app --reload
```

✅ 看到类似 `Running on http://127.0.0.1:5000` 表示启动成功

**保持这个窗口打开，不要关闭！**

---

### 启动前端

**在第二个终端窗口（frontend 目录）：**

```bash
# 启动开发服务器
npm run dev
```

✅ 看到类似以下信息表示启动成功：
```
  VITE v4.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

### 访问应用

打开浏览器，访问：

- **前端页面：** http://localhost:5173
- **后端 API：** http://localhost:5000（根据实际端口调整）

🎉 **恭喜！项目已成功启动！**

---

## ❓ 常见问题

### 1. `python` 不是内部或外部命令

**原因：** Python 未安装或未添加到环境变量

**解决方法：**
- Windows：重新安装 Python，务必勾选 "Add Python to PATH"
- 或手动添加 Python 路径到系统环境变量

---

### 2. `npm` 安装依赖很慢或失败

**解决方法：**
```bash
# 使用淘宝镜像
npm config set registry https://registry.npmmirror.com

# 清除缓存重试
npm cache clean --force
npm install
```

---

### 3. 虚拟环境激活失败（Windows）

**错误：** 无法加载文件，因为在此系统上禁止运行脚本

**解决方法：**
1. 以管理员身份打开 PowerShell
2. 执行：
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
3. 输入 `Y` 确认
4. 重新激活虚拟环境

---

### 4. 端口已被占用

**错误：** Address already in use

**解决方法：**

**方案一：关闭占用端口的程序**
```bash
# Windows 查看占用端口的进程
netstat -ano | findstr :5000
taskkill /PID 进程号 /F

# macOS/Linux
lsof -i :5000
kill -9 进程号
```

**方案二：修改端口**
- 后端：修改 `main.py` 中的端口号
- 前端：修改 `vite.config.js` 中的 `port`

---

### 5. `node_modules` 文件夹太大

**正常现象！** `node_modules` 包含所有依赖包，通常有 100-300MB。

**不要删除：** 项目运行时必需
**可以删除：** 如果空间不足，删除后重新 `npm install` 即可

---

### 6. 跨域错误（CORS）

**现象：** 前端请求后端时报跨域错误

**解决方法：** 在后端代码中配置 CORS

**Flask 示例：**
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许所有来源
```

**FastAPI 示例：**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 7. 依赖安装失败

**尝试以下步骤：**

1. 删除依赖文件夹和锁定文件：
   ```bash
   # 前端
   rm -rf node_modules package-lock.json
   npm install
   
   # 后端
   rm -rf .venv
   python -m venv .venv
   source .venv/bin/activate  # 或 .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. 更新 pip 和 npm：
   ```bash
   python -m pip install --upgrade pip
   npm install -g npm
   ```

---

## 📞 需要帮助？

如果遇到问题：

1. 检查错误信息，复制关键部分到搜索引擎
2. 查看项目的 [Issues](https://github.com/你的用户名/你的仓库名/issues)
3. 联系项目维护者或团队成员

---

## 📝 常用命令速查

### 后端命令
```bash
cd backend
.venv\Scripts\activate          # 激活虚拟环境（Windows）
source .venv/bin/activate       # 激活虚拟环境（macOS/Linux）
python main.py                  # 启动后端
pip install -r requirements.txt # 安装依赖
pip freeze > requirements.txt   # 导出依赖
deactivate                      # 退出虚拟环境
```

### 前端命令
```bash
cd frontend
npm install                     # 安装依赖
npm run dev                     # 启动开发服务器
npm run build                   # 构建生产版本
npm run preview                 # 预览生产构建
```

---

## ✅ 检查清单

安装完成后，确认以下事项：

- [ ] Git 已安装并配置
- [ ] Python 3.8+ 已安装
- [ ] Node.js 16+ 已安装
- [ ] 项目已成功克隆
- [ ] 后端虚拟环境已创建并激活
- [ ] 后端依赖已安装
- [ ] 前端依赖已安装
- [ ] 后端服务已启动（无报错）
- [ ] 前端服务已启动（无报错）
- [ ] 浏览器可以访问 http://localhost:5173

---

**祝你使用愉快！** 🎉

如有问题，欢迎提 Issue 或联系开发者。
```

---

## 💡 使用建议

1. **替换占位符：**
   - 将 `你的用户名` 和 `你的仓库名` 替换成实际的 GitHub 信息
   - 根据实际使用的框架调整启动命令（Flask/FastAPI/Django 等）

2. **补充项目特定信息：**
   - 添加项目截图
   - 说明具体的功能特性
   - 列出详细的依赖包

3. **测试 README：**
   - 找个完全不懂的同学按照文档操作
   - 记录他们遇到的问题
   - 补充到常见问题部分

这个 README 足够详细，即使是第一次接触编程的新手也能跟着步骤完成安装！