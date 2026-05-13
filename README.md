# SprintMind

基于多智能体技术的软件项目管理 AI 助手平台。

本项目面向软件工程课程项目或小型团队协作场景，提供：

- 需求分析
- Sprint 任务规划
- 风险控制与答辩准备
- 本地知识库检索
- 项目资料上传与 OCR
- 图片辅助理解

当前版本的主文本模型使用 `DeepSeek`，图片理解可选接入 `智谱视觉 API`，本地向量检索与 Embedding 支持 `NVIDIA GPU` 加速。

## 技术栈

- 前端：`Vue 3` + `Vite`
- 后端：`FastAPI`
- LLM：`DeepSeek API`
- 图片理解：`ZhipuAI Vision API`（可选）
- 向量库：`Qdrant Local`
- Embedding：`BAAI/bge-small-zh-v1.5`
- OCR：`RapidOCR`
- PDF 处理：`pdfplumber` + `PyMuPDF`

## 目录结构

```text
MyAgent/
├─ agent/                  多智能体协作逻辑
├─ config/                 配置
├─ core/                   LLM、Embedding、Qdrant 等核心能力
├─ frontend/               Vue 前端
├─ knowledge/              文档加载、OCR、知识库处理
├─ memory/                 会话、任务、记忆模块
├─ data/                   本地数据目录
├─ main.py                 FastAPI 后端入口
├─ environment.yml         Conda 环境定义
├─ requirements.txt        后端 Python 依赖
├─ requirements.cuda.txt   CUDA 版 PyTorch 安装入口
└─ .env.example            环境变量模板
```

## 运行环境

推荐环境：

- Windows 10 / 11
- Conda / Miniconda
- Python `3.12`
- Node.js `20+`
- NVIDIA 显卡（可选，用于 Embedding 加速）

## 1. 拉取项目

```bash
git clone <your-repo-url>
cd MyAgent
```

## 2. 创建 Conda 环境

```bash
conda env create -f environment.yml
conda activate myagent
```

如果你已经创建过环境，也可以直接：

```bash
conda activate myagent
```

## 3. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

## 4. 配置环境变量

不要直接把你本地的真实 `.env` 发给别人。

先复制模板：

### Windows CMD

```cmd
copy .env.example .env
```

### PowerShell

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少补这几个值：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=你的 DeepSeek Key
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING_MODE=disabled

ZHIPUAI_API_KEY=你的智谱 Key（可选）
ZHIPUAI_VISION_MODEL=glm-4.6v-flash
```

说明：

- `DEEPSEEK_API_KEY`：必填，否则后端无法启动主聊天能力
- `ZHIPUAI_API_KEY`：可选，不填时图片理解会降级为 OCR + 提示，不影响文本问答

## 5. 可选：安装 CUDA 版 PyTorch

如果你的电脑有 NVIDIA 显卡，并希望让本地 Embedding 尽量跑在 GPU 上：

```bash
python -m pip install -r requirements.cuda.txt
```

验证 GPU：

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

如果输出中 `torch.cuda.is_available()` 为 `True`，说明 GPU 已启用。

## 6. 启动后端

### 推荐：Windows CMD

```cmd
conda activate myagent
cd /d D:\CMM\MyAgent
python main.py
```

### PowerShell

```powershell
conda activate myagent
Set-Location D:\CMM\MyAgent
python main.py
```

正常启动后你会看到：

```text
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

## 7. 启动前端

新开一个终端窗口：

### Windows CMD

```cmd
conda activate myagent
cd /d D:\CMM\MyAgent\frontend
npm run dev
```

### PowerShell

```powershell
conda activate myagent
Set-Location D:\CMM\MyAgent\frontend
npm run dev
```

正常启动后，Vite 会给出一个本地地址，例如：

```text
http://127.0.0.1:5173/
```

## 8. 访问地址

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/health`
- 后端接口基地址：`http://127.0.0.1:8000`

## 9. 如何确认已经跑起来

### 后端

访问：

```text
http://127.0.0.1:8000/health
```

理想情况下你应该能看到：

- `config.ok = true`
- `llm.ok = true`
- `embedding.ok = true`

### 前端

前端打开后应能：

- 正常显示侧边栏和聊天区
- 发送消息后出现阶段状态流式反馈
- 上传 PDF 后能看到知识库资料卡片

## 10. 常见问题

### 10.1 Qdrant 锁冲突

如果启动时报错：

```text
Storage folder ./data/local_qdrant is already accessed by another instance of Qdrant client
```

说明还有一份旧的 Python 后端进程没有退出。

先结束旧进程：

### CMD

```cmd
taskkill /F /IM python.exe
taskkill /F /IM pythonw.exe
```

### PowerShell

```powershell
Get-Process python | Stop-Process -Force
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
```

然后重新启动后端即可。

### 10.2 8000 端口被占用

检查：

```cmd
netstat -ano | findstr :8000
```

如果有输出，说明旧服务还在。

### 10.3 PowerShell 无法执行脚本

如果 `conda activate` 在 PowerShell 中报执行策略错误，优先直接使用 `CMD` 启动项目。  
本项目在 Windows 下推荐用 `CMD`，最省事。

### 10.4 回答速度慢

影响速度的主要因素有：

- 主模型是否使用 `deepseek-v4-pro`
- 问题是否会触发完整多智能体工作流
- 上传资料后的检索与任务同步

如果你更看重速度而不是最强质量，可以把 `.env` 中：

```env
DEEPSEEK_MODEL=deepseek-v4-pro
```

改成更快的模型，例如 DeepSeek 的更轻量版本。

### 10.5 GPU 没有明显跑满

这不一定是异常：

- 主文本模型现在走的是 `DeepSeek API`，推理在云端，不在本机 GPU 上
- 本机 GPU 主要用于 `Embedding`
- 所以你会看到 GPU 使用有提升，但不会像本地大模型那样长期高占用

### 10.6 图片理解不生效

如果没有配置：

```env
ZHIPUAI_API_KEY=
```

那么图片理解会降级为：

- OCR 提取文字
- 视觉理解返回提示信息

这属于正常行为。

## 11. 可选：运行旧版 Streamlit 界面

如果你想运行项目里保留的旧版 Python UI：

```bash
python -m pip install -r requirements.streamlit.txt
streamlit run app_streamlit.py
```

这不是当前推荐主入口，默认还是：

- 前端：Vue
- 后端：FastAPI

## 12. 推荐启动顺序

每次开发建议按这个顺序来：

1. `conda activate myagent`
2. 启动后端 `python main.py`
3. 新开终端，进入 `frontend/`
4. `npm run dev`

## 13. 分享给别人之前

请确认：

- 不要提交真实 `.env`
- 只提交 `.env.example`
- 如果你已经在本地 `.env` 中填过真实 API Key，建议先自行更换 / 轮换密钥

---

如果你在启动过程中遇到报错，建议优先把下面三样信息贴出来：

- 后端终端完整报错
- `http://127.0.0.1:8000/health` 的返回
- 前端浏览器控制台报错
