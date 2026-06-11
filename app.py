"""English Learning Blog — Flask + Markdown + User System"""
import os
import secrets
from datetime import datetime
from flask import Flask, render_template, abort, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension

from models import db, User, Comment, Like, Favorite

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'data', 'blog.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "请先登录"

POSTS_DIR = os.path.join(basedir, "posts")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Post helpers (unchanged) ────────────────────────────────────────────

def parse_post(filepath: str) -> dict | None:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    meta = {}
    body = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2].strip()

    slug = os.path.splitext(os.path.basename(filepath))[0]

    md = markdown.Markdown(
        extensions=[
            FencedCodeExtension(),
            CodeHiliteExtension(guess_lang=False),
            "tables", "toc", "nl2br",
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
    tags = set()
    for post in get_all_posts():
        for tag in post.get("tags", []):
            tags.add(tag)
    return sorted(tags)


def get_post_stats(slug: str) -> dict:
    """Get like/favorite counts for a post."""
    return {
        "likes": Like.query.filter_by(post_slug=slug).count(),
        "favorites": Favorite.query.filter_by(post_slug=slug).count(),
        "comments": Comment.query.filter_by(post_slug=slug).count(),
    }


def user_has_liked(slug: str) -> bool:
    if not current_user.is_authenticated:
        return False
    return Like.query.filter_by(post_slug=slug, user_id=current_user.id).first() is not None


def user_has_favorited(slug: str) -> bool:
    if not current_user.is_authenticated:
        return False
    return Favorite.query.filter_by(post_slug=slug, user_id=current_user.id).first() is not None


# ── Context processor ───────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {"current_user": current_user}


# ── Auth routes ─────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        errors = []
        if not username or len(username) < 2:
            errors.append("用户名至少 2 个字符")
        if not email or "@" not in email:
            errors.append("请输入有效的邮箱")
        if len(password) < 6:
            errors.append("密码至少 6 位")
        if password != confirm:
            errors.append("两次密码不一致")

        if User.query.filter_by(username=username).first():
            errors.append("用户名已被占用")
        if User.query.filter_by(email=email).first():
            errors.append("邮箱已被注册")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("注册成功，欢迎！", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            flash("登录成功", "success")
            return redirect(next_page or url_for("index"))
        flash("用户名或密码错误", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("index"))


# ── Page routes ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    tag = request.args.get("tag", "")
    posts = get_all_posts()
    if tag:
        posts = [p for p in posts if tag in p.get("tags", [])]
    # Attach stats to each post
    for p in posts:
        p["stats"] = get_post_stats(p["slug"])
    return render_template("index.html", posts=posts, current_tag=tag, tags=get_all_tags())


@app.route("/post/<slug>")
def post(slug: str):
    filepath = os.path.join(POSTS_DIR, f"{slug}.md")
    if not os.path.isfile(filepath):
        abort(404)

    post = parse_post(filepath)
    post["stats"] = get_post_stats(slug)
    post["liked"] = user_has_liked(slug)
    post["favorited"] = user_has_favorited(slug)

    comments = (
        Comment.query.filter_by(post_slug=slug)
        .order_by(Comment.created_at.desc())
        .all()
    )

    all_posts = get_all_posts()
    idx = next((i for i, p in enumerate(all_posts) if p["slug"] == slug), -1)
    prev_post = all_posts[idx + 1] if idx + 1 < len(all_posts) else None
    next_post = all_posts[idx - 1] if idx > 0 else None

    return render_template(
        "post.html",
        post=post,
        comments=comments,
        prev_post=prev_post,
        next_post=next_post,
    )


@app.route("/about")
def about():
    return render_template("about.html")


# ── Action routes (AJAX / form posts) ───────────────────────────────────

@app.route("/post/<slug>/like", methods=["POST"])
@login_required
def toggle_like(slug: str):
    existing = Like.query.filter_by(post_slug=slug, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"liked": False, "count": Like.query.filter_by(post_slug=slug).count()})
    db.session.add(Like(post_slug=slug, user_id=current_user.id))
    db.session.commit()
    return jsonify({"liked": True, "count": Like.query.filter_by(post_slug=slug).count()})


@app.route("/post/<slug>/favorite", methods=["POST"])
@login_required
def toggle_favorite(slug: str):
    existing = Favorite.query.filter_by(post_slug=slug, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"favorited": False, "count": Favorite.query.filter_by(post_slug=slug).count()})
    db.session.add(Favorite(post_slug=slug, user_id=current_user.id))
    db.session.commit()
    return jsonify({"favorited": True, "count": Favorite.query.filter_by(post_slug=slug).count()})


@app.route("/post/<slug>/comment", methods=["POST"])
@login_required
def add_comment(slug: str):
    content = request.form.get("content", "").strip()
    if not content or len(content) < 2:
        flash("评论内容不能为空", "error")
        return redirect(url_for("post", slug=slug))

    comment = Comment(post_slug=slug, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    flash("评论发表成功", "success")
    return redirect(url_for("post", slug=slug))


@app.route("/post/<slug>/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(slug: str, comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment and comment.user_id == current_user.id:
        db.session.delete(comment)
        db.session.commit()
        flash("评论已删除", "info")
    return redirect(url_for("post", slug=slug))


# ── Error handlers ──────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ── Init DB ─────────────────────────────────────────────────────────────

def init_db():
    os.makedirs(os.path.join(basedir, "data"), exist_ok=True)
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
