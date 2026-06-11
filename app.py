"""English Learning Blog - Flask + Markdown"""
import os
import re
from datetime import datetime
from flask import Flask, render_template, abort, request
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension

app = Flask(__name__)
POSTS_DIR = os.path.join(os.path.dirname(__file__), "posts")


def parse_post(filepath: str) -> dict | None:
    """Parse a markdown post file. Returns dict with metadata and content."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    meta = {}
    body = raw

    # Parse YAML-like front matter (between --- lines)
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2].strip()

    # Derive slug from filename
    slug = os.path.splitext(os.path.basename(filepath))[0]

    # Markdown to HTML
    md = markdown.Markdown(
        extensions=[
            FencedCodeExtension(),
            CodeHiliteExtension(guess_lang=False),
            "tables",
            "toc",
            "nl2br",
        ]
    )
    html = md.convert(body)

    return {
        "slug": slug,
        "title": meta.get("title", slug.replace("-", " ").title()),
        "date": meta.get("date", ""),
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "summary": meta.get("summary", ""),
        "html": html,
    }


def get_all_posts() -> list[dict]:
    """Load all posts, sorted by date descending."""
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts

    for fname in sorted(os.listdir(POSTS_DIR), reverse=True):
        if fname.endswith(".md"):
            filepath = os.path.join(POSTS_DIR, fname)
            post = parse_post(filepath)
            if post:
                posts.append(post)

    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


def get_all_tags() -> list[str]:
    """Get unique tags from all posts."""
    tags = set()
    for post in get_all_posts():
        for tag in post.get("tags", []):
            tags.add(tag)
    return sorted(tags)


@app.route("/")
def index():
    tag = request.args.get("tag", "")
    posts = get_all_posts()
    if tag:
        posts = [p for p in posts if tag in p.get("tags", [])]
    return render_template("index.html", posts=posts, current_tag=tag, tags=get_all_tags())


@app.route("/post/<slug>")
def post(slug: str):
    filepath = os.path.join(POSTS_DIR, f"{slug}.md")
    if not os.path.isfile(filepath):
        abort(404)

    post = parse_post(filepath)

    # Find next/prev posts
    all_posts = get_all_posts()
    idx = next((i for i, p in enumerate(all_posts) if p["slug"] == slug), -1)
    prev_post = all_posts[idx + 1] if idx + 1 < len(all_posts) else None
    next_post = all_posts[idx - 1] if idx > 0 else None

    return render_template(
        "post.html", post=post, prev_post=prev_post, next_post=next_post
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
