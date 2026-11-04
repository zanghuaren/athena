# 雅典娜

挑战杯参赛作品：面向初中数学、物理、英语的 AI 学习助手，学生端 + 教师端，Android + Web。

通用编码规则见 @AGENT.md，开发流程见 [docs/开发总则.md](docs/开发总则.md)。

## 文档是依据

- 需求、页面、接口、表结构都以 `docs/` 为准：[02 功能需求](docs/02-功能需求.md)、[03 流程与原型](docs/03-流程与原型.md)、[04 UI 设计](docs/04-UI设计.md)、[05 技术方案](docs/05-技术方案.md)、[05 数据库设计](docs/05-数据库设计.md)、[05 接口约定](docs/05-接口约定.md)
- 代码要和文档不一样时，先改文档（或先问），再改代码
- 页面骨架和交互沿用原型 `docs/prototype/index.html`；觉得原设计不合理，要提出来问，不要自行改掉
- `reference/` 是旧项目，只读参考，不从里面复制代码结构

## 目录结构

只在下面这些位置放代码，新增顶层目录或新的分层前先问：

```text
docs/        阶段文档、原型
web/         客户端（React + Vite + Capacitor）
  src/api/         接口客户端；schema.d.ts 是生成物，不手改
  src/styles/      全局样式和设计变量（来自原型 :root）
  src/components/  跨页面复用的组件
  src/pages/       按页面 ID 分目录：common/ student/ teacher/
  src/lib/         与页面无关的工具（存储、格式化等）
  android/         Capacitor 生成的工程
server/      后端（FastAPI，API 与 Worker 同一份代码）
  app/api/         路由，按模块一个文件；只做参数接收、权限、调用 service
  app/schemas/     接口的请求和响应模型（Pydantic）
  app/models/      数据表（SQLAlchemy）
  app/services/    业务逻辑，不依赖 FastAPI
  app/ai/          模型调用、输出结构
  app/jobs/        长任务处理函数
  prompts/         提示词文件
  seed/            预置数据
  migrations/      Alembic 迁移
  tests/           pytest，连真实 PostgreSQL
eval/        评测集和脚本
deploy/      Compose、nginx 配置（不含域名和密钥）
```

- 文件按模块命名，与接口约定的模块对应（`auth`、`mistakes`、`homeworks`……），不建 `utils.py`、`helpers.py`、`common.py` 这类杂物文件
- 不留临时文件、调试脚本、注释掉的代码；一次性脚本用完就删
- 生成物（`web/src/api/schema.d.ts`）只能通过命令重新生成

## 开发方式

- **按层推进，每层一次提交**：一层做完、测试通过就提交，方便回退。一层的范围以“可以独立验证”为准，比如“账号接口 + 测试”“登录注册页”
- 提交信息用中文，格式 `类型(范围): 说明`，类型取 `feat` / `fix` / `refactor` / `test` / `docs` / `chore`，范围取 `server` / `web` / `deploy` / `docs`
- 只提交到本地，不 push
- 域名、隧道、密钥不进仓库（包括文档和提交信息）

## 常用命令

```bash
# 后端开发环境（db + api，代码热重载，api 在 127.0.0.1:8000）
docker compose -f deploy/compose.dev.yml up -d --build
# 后端测试 / 检查
docker compose -f deploy/compose.dev.yml run --rm api pytest
docker compose -f deploy/compose.dev.yml run --rm api ruff check .
# 新迁移（改完 models 后生成，再人工检查）
docker compose -f deploy/compose.dev.yml run --rm api alembic revision --autogenerate -m "说明"

# 前端（在 web/ 下；dev 服务器把 /api 代理到 127.0.0.1:8000）
npm run dev
npm run gen:api     # 后端接口变化后重新生成类型（需要 api 在运行）
npm run lint && npm run typecheck && npm test
```
