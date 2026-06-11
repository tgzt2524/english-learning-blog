# English Learning Blog 📚

A personal blog for documenting my English learning journey. Built with **Flask + Markdown** — write posts as simple `.md` files, no database needed.

## Features

- 📝 **Markdown posts** — just drop `.md` files in `posts/`
- 🏷️ **Tag filtering** — organize posts by topics
- 🎨 **Clean design** — responsive, readable, no bloat
- 🐳 **Docker deployment** — one command to run

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Open in browser
open http://localhost:5000
```

## Docker

```bash
docker compose up -d
```

Visit `http://localhost:5000`

## Adding a Post

Create a `.md` file in `posts/` with front matter:

```markdown
---
title: Your Post Title
date: 2026-06-11
tags: grammar, tips
summary: A short description for the homepage.
---

Your content here...
```

## Project Structure

```
english-learning-blog/
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── posts/              # Markdown blog posts
│   ├── hello-world.md
│   └── ...
├── templates/          # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── post.html
│   └── about.html
└── static/
    └── style.css
```

## License

MIT — feel free to use, modify, and share.
