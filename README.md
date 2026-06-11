# 英语学习博客 📚

记录英语学习历程的个人博客。基于 **Flask + Markdown** 构建 — 把文章写成 `.md` 文件即可发布，无需数据库。

## 功能

- 📝 **Markdown 写文章** — 在 `posts/` 目录下放入 `.md` 文件即可
- 🏷️ **标签筛选** — 按主题分类浏览
- 🎨 **简洁设计** — 响应式、阅读友好、无冗余
- 🐳 **Docker 一键部署** — 一条命令跑起来

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 本地运行
python app.py

# 浏览器打开
open http://localhost:5000
```

## Docker 部署

```bash
docker compose up -d
```

访问 `http://localhost:5000`

## 写文章

在 `posts/` 目录下创建 `.md` 文件，带上 front matter：

```markdown
---
title: 文章标题
date: 2026-06-11
tags: 语法, 技巧
summary: 显示在首页的简短摘要。
---

正文内容……
```

## 目录结构

```
english-learning-blog/
├── app.py              # Flask 应用
├── requirements.txt    # Python 依赖
├── Dockerfile
├── docker-compose.yml
├── posts/              # Markdown 文章
│   ├── hello-world.md
│   └── ...
├── templates/          # Jinja2 模板
│   ├── base.html
│   ├── index.html
│   ├── post.html
│   └── about.html
└── static/
    └── style.css
```

## 开源协议

MIT — 随意使用、修改和分享。
