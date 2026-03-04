# 销售部门每日业绩统计系统（MVP）

一个可快速上线的 MVP：
- 网页上传手写白板照片
- 自动识别业绩数据并入库
- 按规则自动计算每日排名与销冠
- 自动生成前三喜报图片

## 排名规则
按以下优先级降序排序：
1. 成交量（`deal_count`）
2. 高意向客户数（`high_intent_count`）
3. 私域新增数（`private_domain_new`）

## 技术栈
- 后端：FastAPI
- 存储：SQLite（MVP）
- OCR：OpenAI 视觉模型（可配置）
- 喜报：Pillow 动态生成 PNG
- 前端：原生 HTML/CSS/JS

## 本地运行

### 1) 安装依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 配置环境变量
```bash
cp .env.example .env
# 填写 OPENAI_API_KEY
```

### 3) 启动
```bash
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8000
```

访问：`http://localhost:8000`

## API 概览
- `POST /api/upload` 上传白板照片并自动识别入库
  - Query: `report_date=YYYY-MM-DD`（可选）
  - Form: `file`
- `POST /api/manual-submit` 人工修正后提交
- `GET /api/ranking?report_date=YYYY-MM-DD` 查询当日排名与喜报

## 云端快速部署（Render 示例）
1. 将代码推送到 Git 仓库。
2. 在 Render 新建 `Web Service`，环境选择 `Docker`。
3. 配置环境变量：
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`（默认 `gpt-4o-mini`）
   - `POSTER_FONT_PATH`（建议配中文字体路径）
4. 点击部署，完成后即可通过域名访问。

## Vercel 部署（你当前可直接用）

### 0) 已内置的 Vercel 适配
- 已添加 `api/index.py` 作为 Vercel Python 入口
- 已添加 `vercel.json`，把所有路由转发到 FastAPI
- 已加上传大小兜底（默认 4MB）

### 1) 推送到 GitHub
```bash
git add .
git commit -m "feat: sales mvp with vercel deployment config"
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
git push -u origin main
```

### 2) 在 Vercel 导入项目
1. 登录 Vercel，点击 `Add New -> Project`
2. 选择你刚创建的 GitHub 仓库并导入
3. Framework 选择 `Other`
4. Root Directory 保持默认（仓库根目录）
5. Build / Output 不需要额外填写

### 3) 配置环境变量
在 Vercel 项目设置里添加：
- `OPENAI_API_KEY` = 你的密钥
- `OPENAI_MODEL` = `gpt-4o-mini`
- `OPENAI_BASE_URL` = `https://api.openai.com/v1`
- `DATA_DIR` = `/tmp/sales_mvp_data`
- `DB_PATH` = `/tmp/sales_mvp_data/sales_mvp.db`
- `MAX_UPLOAD_BYTES` = `4000000`
- `POSTER_FONT_PATH` = `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`（可先不填）

### 4) 点击 Deploy
部署完成后，用 Vercel 分配的域名直接访问（根路径 `/`）。

### 5) 你需要知道的 MVP 限制
- 当前 Vercel 方案是“快速可用”，`/tmp` 属于临时存储，实例重启后数据可能丢失
- 为了长期稳定，下一步建议把 `SQLite` 换成 `PostgreSQL`，图片换对象存储
- 上传白板图建议压缩到 4MB 内

## 目录结构
```txt
app/
  main.py
  config.py
  db.py
  services/
    ocr_service.py
    poster_service.py
  static/
    index.html
    styles.css
    app.js
requirements.txt
Dockerfile
```

## 后续建议（MVP 之后）
- 改为 PostgreSQL（云端持久化更稳定）
- 增加账号体系与权限
- 支持多门店/多团队隔离
- OCR 低置信度自动进入人工审核队列
- 自动消息推送（企微/钉钉）
