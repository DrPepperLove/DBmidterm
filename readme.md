# 墨香书院 — 在线图书管理系统

基于 B/S 架构的在线图书管理系统，采用 Flask + SQL Server 技术栈，支持读者借阅归还、预约、评论以及管理员后台管理。

## 项目结构

```
DBmidterm/
├── app.py                  # Flask 后端（路由 + 业务逻辑）
├── db.py                   # 数据库抽象层（pyodbc → SQL Server）
├── init_db.py              # 数据库初始化（基于 a.sql 建表 + 种子数据）
├── doc.md                  # 课程设计文档（ER 图、范式、SQL 设计）
├── a.sql                   # PowerDesigner 导出的参考 DDL（Sybase 方言）
├── templates/
│   ├── base.html           # 基础布局（导航栏 + 页脚）
│   ├── index.html          # 首页（热门图书 + 评分排行 + 分类）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── books.html          # 图书浏览 / 搜索 / 分类筛选
│   ├── book_detail.html    # 图书详情 + 评论 + 借阅 / 预约操作
│   ├── my_borrows.html     # 我的借阅记录
│   ├── my_reservations.html# 我的预约记录
│   └── admin/
│       ├── dashboard.html  # 管理概览（统计卡片 + 逾期列表）
│       ├── users.html      # 用户管理（查看 + 删除）
│       ├── books.html      # 图书 CRUD（添加 / 编辑 / 删除）
│       ├── categories.html # 分类管理（添加 / 编辑 / 删除）
│       ├── borrows.html    # 借阅记录管理（强制归还）
│       └── reservations.html# 预约记录查看
└── static/
    ├── css/style.css       # 统一样式（白底 + 深红主题，响应式）
    └── js/main.js          # 前端脚本（Toast 通知、动画、AJAX）
```

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 用户 | 注册 / 登录 | SHA-256 密码哈希，区分 reader / admin 角色 |
| 图书 | 浏览 / 搜索 | 按分类筛选 + 书名 / 作者模糊搜索 |
| 图书 | 详情 | 馆藏副本、平均评分、评论列表 |
| 借阅 | 借书 | 事务保护：检查副本 → 扣减库存 → 插入记录 |
| 借阅 | 还书 | 更新状态 → 恢复库存 → 自动通知预约用户 |
| 预约 | 预约 / 取消 | 副本为 0 时可预约，归还后自动变为可借 |
| 评论 | 评分 + 评论 | 仅借阅并归还后可评，一人一书仅一条（UNIQUE 约束） |
| 首页 | 热门 Top 5 | 基于借阅次数统计 |
| 首页 | 高分推荐 | 平均评分排行（来自视图） |
| 管理 | 仪表盘 | 用户数 / 图书数 / 在借数 / 预约数 / 逾期列表 |
| 管理 | 用户管理 | 查看所有用户，删除非管理员用户 |
| 管理 | 图书管理 | 图书 CRUD（含分类关联） |
| 管理 | 分类管理 | 分类 CRUD |
| 管理 | 借阅管理 | 查看所有记录，强制归还 |
| 管理 | 预约管理 | 查看所有预约 |

## 数据库设计

完全对应 [doc.md](doc.md) 中的设计，满足第三范式（3NF）。

### 表（6 张）

| 表名 | 说明 | 关键约束 |
|------|------|----------|
| `user` | 用户 | username UNIQUE, role CHECK, IDENTITY PK |
| `category` | 图书分类 | IDENTITY PK |
| `book` | 图书 | isbn UNIQUE, FK → category, DEFAULT 1 副本 |
| `borrow_record` | 借阅记录 | FK → user/book, status CHECK |
| `review` | 评论 | FK → user/book, rating CHECK(1-5), UNIQUE(user,book) |
| `reservation` | 预约 | FK → user/book, status CHECK |

### 视图（2 个）

- `view_borrow_details` — 借阅明细（关联用户名 + 书名）
- `view_book_rating` — 图书评分统计（平均分 + 评论数）

### 索引（11 个）

外键索引（borrow_FK, borrowed_FK, reserve_FK, reserved_FK, comment_FK, commeted_FK）+ 复合索引（借阅状态、预约状态）+ 模糊搜索索引（书名、作者）

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3 + Flask |
| 数据库 | SQL Server（通过 pyodbc + ODBC Driver 17） |
| 前端 | HTML5 + CSS3 + Vanilla JS（无前端框架） |
| 样式 | 自定义白底深红主题（CSS 变量 + 响应式布局） |
| 认证 | Flask session + SHA-256 密码哈希 |

## 快速启动

### 1. 环境要求

- Python 3.10+
- SQL Server（本地或远程，支持 Windows 集成认证）
- ODBC Driver 17 for SQL Server

### 2. 安装依赖

```bash
pip install flask pyodbc
```

### 3. 初始化数据库

```bash
cd DBmidterm
python init_db.py
```

脚本会连接到本地 SQL Server，自动创建 `bookstore` 数据库，建表建视图建索引，并插入种子数据。

可通过环境变量覆盖连接参数：

```bash
set DB_SERVER=localhost\SQLEXPRESS   # 默认 localhost
set DB_NAME=bookstore                # 默认 bookstore
```

### 4. 启动应用

```bash
python app.py
```

访问 http://127.0.0.1:5000

### 5. 演示账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | 123456 | 管理员 |
| reader1 | 123456 | 读者 |
| reader2 | 123456 | 读者 |
| reader3 | 123456 | 读者 |

## API 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 首页 | — |
| GET/POST | `/login` | 登录 | — |
| GET/POST | `/register` | 注册 | — |
| GET | `/books` | 图书列表（?category=&keyword=） | — |
| GET | `/book/<id>` | 图书详情 | — |
| POST | `/borrow/<id>` | 借阅 | 登录 |
| POST | `/return/<id>` | 归还 | 登录 |
| GET | `/my-borrows` | 我的借阅 | 登录 |
| POST | `/reserve/<id>` | 预约 | 登录 |
| GET | `/my-reservations` | 我的预约 | 登录 |
| POST | `/review/<id>` | 发表评论 | 登录 |
| GET | `/admin` | 管理仪表盘 | 管理员 |
| GET | `/admin/users` | 用户管理 | 管理员 |
| GET | `/admin/books` | 图书管理 | 管理员 |
| POST | `/admin/books/add` | 添加图书 | 管理员 |
| POST | `/admin/books/<id>/edit` | 编辑图书 | 管理员 |
| POST | `/admin/books/<id>/delete` | 删除图书 | 管理员 |
| GET/POST | `/admin/categories` | 分类管理 | 管理员 |
| GET | `/admin/borrows` | 借阅管理 | 管理员 |
| POST | `/admin/borrows/<id>/force-return` | 强制归还 | 管理员 |
| GET | `/admin/reservations` | 预约管理 | 管理员 |

## 核心实现细节

### 借书事务（[db.py:284-327](db.py#L284-L327)）

```
BEGIN TRANSACTION
  → 检查是否已借此书（防重复）
  → 查询 available_copies（防超借）
  → INSERT borrow_record
  → UPDATE book SET available_copies -= 1
COMMIT / ROLLBACK
```

### 还书 + 预约通知（[db.py:329-370](db.py#L329-L370)）

归还后自动查询该书最早的待处理预约，将其状态更新为「可借」，提示用户有预约者等待。

### 评论权限控制

- 仅归还过该书的用户可评论（[app.py:233](app.py#L233)）
- `UNIQUE(user_id, book_id)` 约束防止重复评论（[init_db.py:109](init_db.py#L109)）

## 设计主题

配色方案「墨香书院」采用白底 + 深红（#8B0012）为主色调，灵感来自传统书院匾额。字体使用 DM Serif Display（标题）+ Source Serif 4 / Noto Sans SC（正文），营造典雅的阅读氛围。
