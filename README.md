# 我的电影库

基于 Flask、SQLAlchemy 和原生 JavaScript 的私人电影库。前后端同源，无需 Node 构建工具。默认使用 SQLite，支持连接已有 MySQL 8+ 服务；本机不需要安装 MySQL。

## 启动

在项目目录运行（Windows PowerShell，Python 3.10+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

打开 <http://127.0.0.1:8000>。已有虚拟环境时直接执行最后一行。端口被占用时：

```powershell
$env:PORT = '8001'
.\.venv\Scripts\python.exe app.py
```

首次启动会创建 `instance/movies.sqlite3`，一次性导入原有 `films.json`。导入保留 ID、名称、评价、备注、已看布尔值和原始顺序，不改写 JSON。后续启动不会重新覆盖数据库，也不会恢复已删除的电影。旧数据中乱码的状态文字按有效的 `watched` 值规范化为“已看 / 未看”。名称不完整和同名条目不会自动删除或合并。

## 功能

- 添加、编辑、删除电影；切换已看 / 未看；状态数量统计。
- 搜索名称、评价、剧情简介和备注；按片单顺序、名称或最近更新时间排序。
- 点击电影卡片，打开名字、完整海报和剧情简介的详情弹窗。
- 弹窗底部独立保存备注，刷新和重启后仍保留，不覆盖电影其他字段。
- 编辑电影的海报链接或上传本地 JPG / PNG / WebP；文件不超过 5 MB、2000 万像素，服务端校验并转为 WebP。
- 上传海报保存在 `instance/posters/`；外部图片失败会显示缺省图片。
- 未保存内容关闭前确认、提交过程禁用重复操作、失败时保留输入、键盘操作及移动端布局。

原始 166 条记录没有海报和剧情字段。`movie_app/catalog.json` 为 6 部名称明确的电影提供海报地址和简介，仅在首次导入时填充缺失字段，不覆盖已有资料。优先使用已有本地海报，否则使用外部图片链接。公开仓库不分发第三方电影海报原图，外部图片需要联网；其余条目显示“暂无海报 / 暂无剧情简介”，可在编辑窗口补充。没有自动联网猜测或抓取匹配。

仅用于个人使用且确认图片使用权限后，可在首次启动前执行 `python scripts/download_posters.py` 缓存这些海报。下载目录已被 Git 忽略，不会上传；现有数据库的海报地址不会因下载而自动改写。

## 数据库

复制 `.env.example` 为 `.env` 并按需填写。默认 SQLite 文件位于 `instance/`，无需额外服务。

如已有远程或容器 MySQL 8+，先在该服务端创建数据库和专用账号，并授予该数据库的建表、查询和增删改权限：

```sql
CREATE DATABASE movies CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```dotenv
DATABASE_URL=mysql+pymysql://movie_user:URL_ENCODED_PASSWORD@server:3306/movies?charset=utf8mb4
```

密码中的 `@`、`:`、`/` 等字符需要 URL 编码。不应提交 `.env` 或数据库密码。SQLite 与 MySQL 共用模型、校验及事务代码，MySQL 使用 `utf8mb4` 保存中文与表情。首次启动自动创建缺失表，也可执行 `python -m flask --app app init-db`。`create_all` 不会更新已存在的表结构；未来模型字段变更需要新增数据库迁移。

**切换数据库不会自动迁移 SQLite 的最新内容。** 应先导出当前数据，在目标数据库导入；若目标已自动导入旧片单，使用 `--update-existing` 明确覆盖匹配 ID。上传海报文件也需随项目迁移。要完全复制包括已删除记录在内的片单，使用空的目标数据库，并在 `.env` 设置 `AUTO_IMPORT=false` 后再导入备份，避免旧片单条目被重新引入；恢复后继续保留该设置。

## 导入、导出与备份

```powershell
# 导出到新文件，不覆盖已有文件
.\.venv\Scripts\python.exe -m flask --app app export-json backup.json

# 添加不存在的 ID；已有电影默认不覆盖
.\.venv\Scripts\python.exe -m flask --app app import-json films.json

# 明确更新匹配 ID；只更新输入中提供的字段，不删除其他电影
.\.venv\Scripts\python.exe -m flask --app app import-json backup.json --update-existing
```

导入先验证完整文件，有非法记录时整批不写入。备份包含海报路径和简介，但不包含海报二进制文件。完整备份应包含 JSON 和 `instance/posters/`，也可在停止服务后备份整个 `instance/`。删除电影不会自动删除已上传文件，以免影响其他引用相同海报的电影；取消编辑产生的未引用上传文件也会保留。

原有 `import_notion.ps1` 和修复脚本仍用于生成、修复 `films.json`，不会直接更改运行中的数据库。执行后使用 `import-json` 导入。Notion 脚本依赖原有的外部非公开接口，重构未改变或验证该外部服务。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q

# 使用已经安装的 Edge，不下载浏览器
.\.venv\Scripts\python.exe -m pytest --run-browser --browser-channel msedge -q
# 已安装 Chrome 时，可将 msedge 换成 chrome
```

默认执行后端测试，浏览器测试需显式启用。测试在临时目录中建立 SQLite，验证旧数据导入与重启、CRUD、状态同步、部分更新、搜索、非法数据、海报上传、来源校验和 JSON 备份。MySQL 测试是 SQLAlchemy MySQL 方言的建表编译检查，**不是实际 MySQL 连接测试**。没有安装或启动 MySQL 服务。

浏览器测试运行独立本地测试服务，覆盖桌面 / 手机 CRUD、上传、详情、备注、刷新持久化、失败保留内容、XSS 文本、缺失海报、键盘和横向溢出检查。截图输出到 `test-results/`，不修改实际片单。

## 结构

```text
app.py                       开发 / WSGI 入口
movie_app/
  __init__.py                应用工厂、配置、初始化与 CLI
  extensions.py              数据库扩展
  models.py                  Movie 与导入标记模型
  services.py                导入与查询服务
  validation.py              数据及图片地址校验
  routes.py                  REST API、页面与海报服务
  catalog.json               部分电影的初始补充资料
  templates/index.html       前端页面
  static/                    前端 JS、CSS、图标、本地图片
tests/                       接口、迁移与浏览器回归测试
scripts/                     图片资源重建脚本
films.json                   保留的原始数据
instance/                    本地运行数据（不提交）
```

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/movies` | 数组形式返回片单，兼容旧接口；可用 `q` 和 `status=all/watched/unwatched` |
| POST | `/api/movies` | 新增，返回 201；未提供 ID 时服务端生成 UUID |
| GET | `/api/movies/<id>` | 电影详情 |
| PUT / PATCH | `/api/movies/<id>` | 更新提供的字段，未提供的字段保留 |
| DELETE | `/api/movies/<id>` | 删除，返回 204 |
| POST | `/api/posters` | multipart 字段 `file` 上传海报，返回 `poster_url` |

电影字段：`id`、`title`（必填，120 字）、`rating`（80 字）、`watched`（布尔）、`status`（由 watched 推导）、`notes`（5000 字）、`poster_url`（2048 字）、`synopsis`（10000 字）、只读的 `created_at` / `updated_at`。旧客户端可以只提交 `status`；同时提交时以 `watched` 为准。更新不能更改 ID。错误为 JSON `{"error": "…"}` 和对应 HTTP 状态码。

## 运行边界

这是无账号的单人本地应用，默认仅监听 `127.0.0.1`，不要直接暴露到公网。提供同源写入检查、CSP、安全响应头和输入校验，但不包含登录、租户隔离或访问权限系统。若部署到远程服务器，应先增加认证、HTTPS、反向代理及数据库备份策略。

需要较稳定的本地 WSGI 服务时，可使用已列入依赖的 Waitress：

```powershell
.\.venv\Scripts\waitress-serve.exe --host=127.0.0.1 --port=8000 app:app
```

前端的 Lucide 图标库和缺省图片均随项目保存，不需要访问 CDN。海报来源及第三方许可见 `THIRD_PARTY_NOTICES.md`。

## 开源许可

项目原创源码采用 [MIT License](LICENSE)，允许使用、修改和再分发，须保留版权和许可声明。Lucide 按其原有许可证分发；第三方电影海报不在 MIT 授权范围内，也不随公开仓库分发。

仓库不包含 `.env`、本地数据库、运行日志、测试输出及用户上传文件。公开的 `films.json` 是初始片单，备注为空；个人运行数据仅保存在被忽略的 `instance/` 中。
