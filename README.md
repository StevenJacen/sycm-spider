# SYCM 市场排行爬虫服务

## 文件说明

- `spider.py` — 核心爬虫脚本（支持环境变量、断点续传）
- `server.py` — Flask 服务入口（定时任务 + REST API）
- `Dockerfile` — Docker 镜像构建文件
- `docker-compose.yml` — Docker Compose 编排文件
- `entrypoint.sh` — 容器启动脚本
- `requirements.txt` — Python 依赖
- `D:/Document/spider/` — Docker 运行后自动生成的结果目录（已映射到容器内 `/app/output`）

---

## 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `COOKIE` | 是 | 从浏览器复制的完整 Cookie 字符串 |
| `TOKEN` | 是 | 从浏览器 URL 复制的 token 参数值 |
| `NOTIFY_URL` | 否 | **企业微信等 Webhook 地址**。Cookie 失效或运行异常时自动推送消息 |
| `WEBHOOK_URL` | 否 | 兼容旧名，同 `NOTIFY_URL` |
| `AUTO_LAST_WEEK` | 否 | 设为 `1` 时自动抓取前一周/前一天数据（默认开启） |
| `DATE_TYPE` | 否 | `week`（按周）或 `day`（按天），默认 `week` |
| `CRON_SCHEDULE` | 否 | 定时规则，默认 `0 3 * * 3`（每周三 03:00） |
| `RUN_ONCE` | 否 | 设为 `1` 时容器启动后立即执行一次（用于测试） |

---

## 本地运行

### 纯命令行模式

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
set COOKIE=xxx
set TOKEN=xxx
set NOTIFY_URL=https://your-server.com/api/notify

# 运行爬虫（默认 week）
python spider.py

# 按天模式抓取前一天
python spider.py day

# 按天模式抓取指定日期范围
python spider.py 20260401 20260415 day

# 按周模式抓取（默认）
python spider.py 20260119 20260315 1101
python spider.py all all week 1101
```

### 服务模式（推荐用于定时任务）

```bash
set COOKIE=xxx
set TOKEN=xxx
set NOTIFY_URL=https://your-server.com/api/notify
python server.py
```

服务默认监听 `http://0.0.0.0:5000`

---

## Docker 部署

### 1. 配置环境变量

在项目目录下创建 `.env` 文件：

```env
COOKIE=你的Cookie字符串
TOKEN=你的token
NOTIFY_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=80b16220-3d78-4efd-93c5-c17cfa92d73e
```

> 通知已适配企业微信机器人 webhook。推送格式：
> ```json
> {
>   "msgtype": "text",
>   "text": {
>     "content": "【SYCM爬虫】COOKIE_EXPIRED\nCookie/Token 已失效，请尽快更新。详情: ...\n时间: 2026-04-16 12:00:00"
>   }
> }
> ```

### 2. 启动容器

```bash
docker-compose up -d --build
```

### 3. API 接口

#### 查看服务状态
```bash
curl http://localhost:5000/health
```

返回示例：
```json
{
  "status": "idle",
  "message": "爬取完成",
  "last_notify": null,
  "date_range": "2026-04-06|2026-04-12"
}
```

#### 更新 Cookie / Token（恢复爬取）
当服务状态为 `waiting_cookie` 时，调用此接口会自动恢复之前中断的爬取：

```bash
curl -X POST http://localhost:5000/update-cookie \
  -H "Content-Type: application/json" \
  -d '{"cookie":"新的Cookie","token":"新的Token"}'
```

返回示例：
```json
{
  "success": true,
  "message": "已更新 cookie，正在恢复爬取",
  "date_range": "2026-04-06|2026-04-12"
}
```

#### 手动触发爬取
```bash
curl -X POST http://localhost:5000/trigger

# 指定日期范围
curl -X POST http://localhost:5000/trigger \
  -H "Content-Type: application/json" \
  -d '{"date_range":"2026-01-19|2026-01-25"}'

# 按天模式触发
curl -X POST http://localhost:5000/trigger \
  -H "Content-Type: application/json" \
  -d '{"date_type":"day"}'
```

### 4. 查看日志

```bash
# 容器实时日志
docker logs -f sycm-spider

# cron / 任务日志（在宿主机映射目录中）
tail -f "D:/Document/spider/cron.log"
```

### 5. 立即测试一次

修改 `docker-compose.yml`：

```yaml
environment:
  - RUN_ONCE=1
```

然后重启：

```bash
docker-compose up -d
```

---

## Cookie 失效流程

1. **定时任务触发** → 服务开始爬取上周数据
2. **Cookie 失效** → `server.py` 立即发送 POST 请求到你的 `NOTIFY_URL`，消息格式如下：
   ```json
   {
     "msgtype": "text",
     "text": {
       "content": "【SYCM爬虫】COOKIE_EXPIRED\nCookie/Token 已失效，请尽快更新。详情: ...\n时间: 2026-04-16 12:00:00"
     }
   }
   ```
3. **服务状态**变为 `waiting_cookie`，暂停后续请求
4. 你收到通知后，调用 `POST /update-cookie` 传入新的 Cookie 和 Token
5. 服务自动**恢复中断的爬取**（利用 `.progress_*.json` 断点续传）

---

## 输出文件

### 本地运行
数据会按 **品类 + 周期** 分文件保存到 `output/` 目录。

### Docker 运行
数据会保存到宿主机映射目录 **`D:/Document/spider/`** 下。

文件名格式：

```
{cateId}_{safe_cate_name}_{date_start}_{date_end}.csv
```

示例：

```
1101_笔记本电脑_2026-04-06_2026-04-12.csv
```

### CSV 附加字段

| 字段名 | 说明 |
|--------|------|
| `_query_date_range` | 周期区间，如 `2026-04-06\|2026-04-12` |
| `_query_date_type` | 固定为 `recent7` |
| `_query_cate_id` | 品类 ID |
| `_query_cate_name` | 品类名称 |
| `_query_rank_type` | `gmv` / `growth` / `newitm_ipv` |
| `_query_price_seg` | 价格段 `1`~`6` |
| `_query_seller_type` | `0` / `1` |
| `_query_page` | 数据所在页码 |

---

## 断点续传

- 每个 `(周期, 品类)` 组合会生成一个 `.progress_{cateId}_{date_range}.json` 进度文件。
- 已完成的 `(rankType, priceSeg, sellerType)` 小组合会在恢复时自动跳过。
- CSV 采用 **append** 模式写入，已抓取的数据不会被覆盖。
- 若字段结构发生变化（如后续出现 `sellerId`），`_append_csv` 会自动扩展表头并重写合并旧数据。
- 若需要完全重跑某个周期+品类，只需删除对应的 `.progress_*.json` 和 `.csv` 文件即可。

---

## 参数说明

| 参数 | 取值 |
|------|------|
| `rankType` | `gmv` / `growth` / `newitm_ipv` |
| `priceSeg` | `1` ~ `6` |
| `sellerType` | `0` / `1` |
| `cateId` | 脚本中内置的 80 个类目 |
