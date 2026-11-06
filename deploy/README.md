# 公网部署

公网实例使用 `compose.prod.yml`：复用现有项目名和数据卷，API/Worker 以非 root 用户运行，源码和容器根目录只读，关闭热重载。前端由非 root nginx 提供构建产物并反向代理 `/api/`，支持原有上传与 SSE。开发仍使用 `compose.dev.yml`。

生产环境文件保留模型配置，并设置独立的高熵 `FILE_SECRET`；环境文件不提交。切换文件签名密钥会使旧图片 URL 失效，重新获取链接即可，图片文件不变。注册、模型额度和资源配额维持现有策略。

切换前检查 `jobs` 没有 queued/running 任务并备份数据库与文件卷；只更新 API、Worker、nginx，不重建或删除数据库/数据卷。前端构建在发布步骤执行，服务启动不隐式构建。

```bash
docker compose -f deploy/compose.prod.yml config --quiet
docker compose -f deploy/compose.prod.yml up -d api worker nginx
```

`compose.prod.yml` 的项目名与原实例相同，用于保留数据库与文件卷。`FILE_SECRET` 从私密环境文件读取。API 文档默认关闭；本地生成接口类型时可临时设置 `EXPOSE_API_DOCS=true`，公网 nginx 始终拒绝文档路径。

原型站通过 `prototype_server.py` 只发布首页和 index.html；历史备份应保存在发布目录之外。
