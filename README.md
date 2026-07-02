# EIQ

这是一个问卷分析项目。前端负责上传文件和展示结果，后端负责读取问卷、整理字段、做统计分析，并生成可以直接查看的分析内容。

仓库里只放正式运行需要的代码。数据文件、模型文件、上传记录、实验脚本和本地缓存都不放进来。

## 目录

```text
backend/   后端接口和分析逻辑
frontend/  前端页面
```

## 后端

在项目根目录运行：

```powershell
pip install fastapi uvicorn python-multipart pandas numpy openpyxl matplotlib scikit-learn openai pydantic
pip install langchain langchain-core langchain-openai sentence-transformers bertopic snownlp keybert huggingface-hub
uvicorn backend.api.api_server:app --reload --host 127.0.0.1 --port 8000
```

如果要调用大模型接口，在本地配置环境变量：

```text
OPENAI_API_KEY=你的接口密钥
```

不要把密钥写进代码，也不要提交 `.env` 文件。

## 前端

另开一个 PowerShell：

```powershell
cd frontend
npm install
npm run dev
```

前端请求默认走 `/api`，本地代理配置在 `frontend/vite.config.js`。
