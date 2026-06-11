"""English Learning Blog — Full Social Platform"""
import os
import re
import json
import secrets
import hashlib
from datetime import datetime, timezone, date
from urllib.parse import urlencode

import requests
from flask import (Flask, render_template, abort, request, redirect,
                   url_for, flash, jsonify, make_response)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension

from models import (db, User, Comment, Reaction, Favorite, Follow,
                    Notification, Badge, UserBadge, PinnedPost)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ── Config ───────────────────────────────────────────────────────────────

basedir = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(basedir, "data")
os.makedirs(DATA_DIR, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'blog.db')}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

POSTS_DIR = os.path.join(basedir, "posts")

# OAuth
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000")

# ── Login Manager ────────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "请先登录"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(
            user_id=current_user.id, is_read=False).count()
    return {"current_user": current_user, "unread_count": unread, "SITE_URL": SITE_URL}


# ── Post Helpers ─────────────────────────────────────────────────────────

def parse_post(filepath: str) -> dict | None:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    meta, body = {}, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()
    slug = os.path.splitext(os.path.basename(filepath))[0]
    md = markdown.Markdown(extensions=[
        FencedCodeExtension(), CodeHiliteExtension(guess_lang=False),
        "tables", "toc", "nl2br"])
    html = md.convert(body)
    return {"slug": slug, "title": meta.get("title", slug.replace("-", " ").title()),
            "date": meta.get("date", ""),
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
            "summary": meta.get("summary", ""), "html": html}


def get_all_posts() -> list[dict]:
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts
    for fname in sorted(os.listdir(POSTS_DIR), reverse=True):
        if fname.endswith(".md"):
            p = parse_post(os.path.join(POSTS_DIR, fname))
            if p:
                posts.append(p)
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


def get_all_tags() -> list[str]:
    tags = set()
    for p in get_all_posts():
        for t in p.get("tags", []):
            tags.add(t)
    return sorted(tags)


def get_post_stats(slug: str) -> dict:
    reactions = Reaction.query.filter_by(post_slug=slug).all()
    rcounts = {}
    for r in reactions:
        rcounts[r.reaction_type] = rcounts.get(r.reaction_type, 0) + 1
    return {
        "reactions": sum(rcounts.values()),
        "likes": rcounts.get("like", 0) + rcounts.get("love", 0),
        "favorites": Favorite.query.filter_by(post_slug=slug).count(),
        "comments": Comment.query.filter_by(post_slug=slug).count(),
        "reaction_breakdown": rcounts,
    }


def user_reaction(slug: str) -> str | None:
    if not current_user.is_authenticated:
        return None
    r = Reaction.query.filter_by(post_slug=slug, user_id=current_user.id).first()
    return r.reaction_type if r else None


def user_has_favorited(slug: str) -> bool:
    if not current_user.is_authenticated:
        return False
    return Favorite.query.filter_by(post_slug=slug, user_id=current_user.id).first() is not None


def is_following(user_id: int) -> bool:
    if not current_user.is_authenticated:
        return False
    return Follow.query.filter_by(
        follower_id=current_user.id, following_id=user_id).first() is not None


def create_notification(user_id: int, actor_id: int, ntype: str, **kwargs):
    if user_id == actor_id:
        return
    n = Notification(user_id=user_id, actor_id=actor_id, notif_type=ntype, **kwargs)
    db.session.add(n)
    db.session.commit()


def check_and_award_badges(user: User):
    """Check and award badges after any action."""
    badge_checks = [
        ("first_comment", "初出茅庐", "发表第一条评论", "💬",
         lambda: Comment.query.filter_by(user_id=user.id).count() >= 1),
        ("first_post", "笔耕不辍", "发表第一篇文章", "✍️",
         lambda: Comment.query.filter_by(user_id=user.id).count() >= 3),
        ("ten_likes", "人气之星", "累计获得10个赞", "❤️",
         lambda: Reaction.query.filter_by(user_id=user.id).count() >= 10),
        ("seven_day_streak", "坚持不懈", "连续7天打卡", "🔥",
         lambda: user.streak_count >= 7),
        ("fifty_points", "社区达人", "累计获得50积分", "🏆",
         lambda: user.total_points >= 50),
    ]
    for key, name, desc, icon, check in badge_checks:
        badge = Badge.query.filter_by(key=key).first()
        if not badge:
            badge = Badge(key=key, name=name, description=desc, icon=icon)
            db.session.add(badge)
            db.session.commit()
        if not UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first():
            if check():
                db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
                db.session.commit()


# ── Auth Routes ──────────────────────────────────────────────────────────

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
            errors.append("请输入有效邮箱")
        if len(password) < 6:
            errors.append("密码至少 6 位")
        if password != confirm:
            errors.append("两次密码不一致")
        if User.query.filter_by(username=username).first():
            errors.append("用户名已占用")
        if User.query.filter_by(email=email).first():
            errors.append("邮箱已注册")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html")

        user = User(username=username, email=email, bio="", streak_count=0)
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
            flash("登录成功", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("用户名或密码错误", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出", "info")
    return redirect(url_for("index"))


# ── GitHub OAuth ─────────────────────────────────────────────────────────

@app.route("/auth/github")
def auth_github():
    if not GITHUB_CLIENT_ID:
        flash("GitHub 登录未配置", "error")
        return redirect(url_for("login"))
    params = {"client_id": GITHUB_CLIENT_ID, "scope": "user:email",
              "redirect_uri": f"{SITE_URL}/auth/github/callback"}
    return redirect(f"https://github.com/login/oauth/authorize?{urlencode(params)}")


@app.route("/auth/github/callback")
def auth_github_callback():
    code = request.args.get("code")
    if not code:
        flash("GitHub 授权失败", "error")
        return redirect(url_for("login"))

    # Exchange code for token
    r = requests.post("https://github.com/login/oauth/access_token",
                      json={"client_id": GITHUB_CLIENT_ID,
                            "client_secret": GITHUB_CLIENT_SECRET, "code": code},
                      headers={"Accept": "application/json"}, timeout=10)
    token = r.json().get("access_token")
    if not token:
        flash("GitHub 授权失败", "error")
        return redirect(url_for("login"))

    # Get user info
    r = requests.get("https://api.github.com/user", timeout=10,
                     headers={"Authorization": f"Bearer {token}"})
    gh_user = r.json()

    # Get email
    r = requests.get("https://api.github.com/user/emails", timeout=10,
                     headers={"Authorization": f"Bearer {token}"})
    emails = r.json()
    primary_email = next((e["email"] for e in emails if e.get("primary")), gh_user.get("email", ""))

    github_id = str(gh_user.get("id"))
    user = User.query.filter_by(github_id=github_id).first()
    if not user:
        username = gh_user.get("login", f"gh_{github_id}")
        if User.query.filter_by(username=username).first():
            username = f"{username}_{github_id}"
        user = User(username=username,
                    email=primary_email or f"{github_id}@github.user",
                    github_id=github_id,
                    avatar_url=gh_user.get("avatar_url", ""),
                    github_username=gh_user.get("login", ""),
                    bio=gh_user.get("bio", "") or "",
                    streak_count=0)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    flash("GitHub 登录成功", "success")
    return redirect(url_for("index"))


# ── Page Routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    tag = request.args.get("tag", "")
    posts = get_all_posts()

    # Pinned posts first
    pinned_slugs = {p.post_slug for p in PinnedPost.query.all()}
    pinned = [p for p in posts if p["slug"] in pinned_slugs]
    regular = [p for p in posts if p["slug"] not in pinned_slugs]

    if tag:
        pinned = [p for p in pinned if tag in p.get("tags", [])]
        regular = [p for p in regular if tag in p.get("tags", [])]

    for p in pinned + regular:
        p["stats"] = get_post_stats(p["slug"])
        p["is_pinned"] = p["slug"] in pinned_slugs

    return render_template("index.html", pinned=pinned, regular=regular,
                           current_tag=tag, tags=get_all_tags())


@app.route("/feed")
@login_required
def feed():
    """Activity feed from followed users."""
    following_ids = [f.following_id for f in
                     Follow.query.filter_by(follower_id=current_user.id).all()]
    if not following_ids:
        following_ids = [current_user.id]  # fallback to own

    recent_comments = (Comment.query
                       .filter(Comment.user_id.in_(following_ids))
                       .order_by(Comment.created_at.desc()).limit(30).all())
    recent_reactions = (Reaction.query
                        .filter(Reaction.user_id.in_(following_ids))
                        .order_by(Reaction.created_at.desc()).limit(20).all())
    recent_favs = (Favorite.query
                   .filter(Favorite.user_id.in_(following_ids))
                   .order_by(Favorite.created_at.desc()).limit(20).all())

    # Merge and sort
    events = []
    for c in recent_comments:
        events.append({"type": "comment", "user": c.author, "post_slug": c.post_slug,
                       "content": c.content[:100], "time": c.created_at})
    for r in recent_reactions:
        events.append({"type": "reaction", "user": r.user, "post_slug": r.post_slug,
                       "reaction": r.reaction_type, "time": r.created_at})
    for fv in recent_favs:
        events.append({"type": "favorite", "user": fv.user, "post_slug": fv.post_slug,
                       "time": fv.created_at})

    events.sort(key=lambda e: e["time"], reverse=True)
    return render_template("feed.html", events=events[:50])


@app.route("/post/<slug>")
def post(slug: str):
    filepath = os.path.join(POSTS_DIR, f"{slug}.md")
    if not os.path.isfile(filepath):
        abort(404)

    p = parse_post(filepath)
    p["stats"] = get_post_stats(slug)
    p["user_reaction"] = user_reaction(slug)
    p["favorited"] = user_has_favorited(slug)

    # Top-level comments
    comments = (Comment.query.filter_by(post_slug=slug, parent_id=None)
                .order_by(Comment.created_at.desc()).all())

    # Build threaded structure
    replies_map = {}
    all_replies = Comment.query.filter(
        Comment.post_slug == slug, Comment.parent_id.isnot(None)
    ).order_by(Comment.created_at.asc()).all()
    for r in all_replies:
        replies_map.setdefault(r.parent_id, []).append(r)

    all_posts = get_all_posts()
    idx = next((i for i, pp in enumerate(all_posts) if pp["slug"] == slug), -1)
    prev_post = all_posts[idx + 1] if idx + 1 < len(all_posts) else None
    next_post = all_posts[idx - 1] if idx > 0 else None

    return render_template("post.html", post=p, comments=comments,
                           replies_map=replies_map,
                           prev_post=prev_post, next_post=next_post,
                           reaction_types=REACTION_TYPES)


@app.route("/profile/<username>")
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    badges = UserBadge.query.filter_by(user_id=user.id).all()
    comments = Comment.query.filter_by(user_id=user.id).order_by(
        Comment.created_at.desc()).limit(20).all()
    return render_template("profile.html", profile_user=user,
                           badges=badges, comments=comments,
                           is_following=is_following(user.id))


@app.route("/notifications")
@login_required
def notifications():
    notifs = (Notification.query.filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    return render_template("notifications.html", notifications=notifs)


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        for p in get_all_posts():
            # Simple full-text search in title + summary + content
            filepath = os.path.join(POSTS_DIR, f"{p['slug']}.md")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().lower()
            if q.lower() in p["title"].lower() or q.lower() in content:
                p["stats"] = get_post_stats(p["slug"])
                results.append(p)
    return render_template("search.html", query=q, results=results)


@app.route("/leaderboard")
def leaderboard():
    top_users = User.query.order_by(User.total_points.desc()).limit(20).all()
    return render_template("leaderboard.html", top_users=top_users)


@app.route("/rss")
def rss_feed():
    posts = get_all_posts()[:20]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0">\n<channel>\n'
    xml += '<title>英语学习博客</title>\n'
    xml += f'<link>{SITE_URL}</link>\n'
    xml += '<description>分享英语学习笔记和资源</description>\n'
    xml += '<language>zh-CN</language>\n'
    for p in posts:
        xml += '<item>\n'
        xml += f'<title>{p["title"]}</title>\n'
        xml += f'<link>{SITE_URL}/post/{p["slug"]}</link>\n'
        xml += f'<description>{p.get("summary", "")}</description>\n'
        if p.get("date"):
            xml += f'<pubDate>{p["date"]}</pubDate>\n'
        xml += '</item>\n'
    xml += '</channel>\n</rss>'
    response = make_response(xml)
    response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
    return response


@app.route("/about")
def about():
    stats = {
        "users": User.query.count(),
        "comments": Comment.query.count(),
        "reactions": Reaction.query.count(),
        "posts": len(get_all_posts()),
    }
    return render_template("about.html", stats=stats)


# ── Action Routes ────────────────────────────────────────────────────────

REACTION_TYPES = ["like", "love", "clap", "wow", "fire", "think"]
REACTION_EMOJI = {"like": "👍", "love": "❤️", "clap": "👏",
                  "wow": "😮", "fire": "🔥", "think": "🤔"}


@app.route("/post/<slug>/react", methods=["POST"])
@login_required
def toggle_reaction(slug: str):
    rtype = request.form.get("type", "like")
    if rtype not in REACTION_TYPES:
        return jsonify({"error": "invalid type"}), 400

    existing = Reaction.query.filter_by(post_slug=slug, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        if existing.reaction_type == rtype:
            # User un-reacted
            return jsonify({"reacted": False, "type": None, "stats": get_post_stats(slug)})

    db.session.add(Reaction(post_slug=slug, user_id=current_user.id, reaction_type=rtype))
    db.session.commit()

    # Award points to author (via post slug lookup — simplified)
    current_user.total_points = (current_user.total_points or 0) + 1
    check_and_award_badges(current_user)
    db.session.commit()

    return jsonify({"reacted": True, "type": rtype, "stats": get_post_stats(slug)})


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
    parent_id = request.form.get("parent_id", type=int)

    if not content or len(content) < 2:
        flash("评论不能为空", "error")
        return redirect(url_for("post", slug=slug))

    comment = Comment(post_slug=slug, user_id=current_user.id,
                      content=content, parent_id=parent_id)
    db.session.add(comment)
    db.session.commit()

    # Notify post author or parent comment author
    if parent_id:
        parent = db.session.get(Comment, parent_id)
        if parent:
            create_notification(parent.user_id, current_user.id, "reply",
                                post_slug=slug, comment_id=comment.id)
    else:
        # Notify post "author" — we don't have a post author model, so skip
        # Instead, extract @mentions from content
        pass

    # Handle @mentions
    import re as re_mod
    mentions = re_mod.findall(r'@(\w+)', content)
    for m in mentions:
        mentioned = User.query.filter_by(username=m).first()
        if mentioned:
            create_notification(mentioned.id, current_user.id, "mention",
                                post_slug=slug, comment_id=comment.id)

    current_user.total_points = (current_user.total_points or 0) + 2
    check_and_award_badges(current_user)
    db.session.commit()

    flash("评论发表成功", "success")
    return redirect(url_for("post", slug=slug))


@app.route("/post/<slug>/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(slug: str, comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment and comment.user_id == current_user.id:
        # Also delete replies
        Comment.query.filter_by(parent_id=comment.id).delete()
        db.session.delete(comment)
        db.session.commit()
        flash("评论已删除", "info")
    return redirect(url_for("post", slug=slug))


@app.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def toggle_follow(user_id: int):
    user = db.session.get(User, user_id)
    if not user or user_id == current_user.id:
        return jsonify({"error": "invalid"}), 400

    existing = Follow.query.filter_by(
        follower_id=current_user.id, following_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"following": False, "count": user.follower_count})

    db.session.add(Follow(follower_id=current_user.id, following_id=user_id))
    create_notification(user_id, current_user.id, "follow")
    db.session.commit()
    return jsonify({"following": True, "count": user.follower_count})


@app.route("/streak/checkin", methods=["POST"])
@login_required
def streak_checkin():
    today = date.today()
    user = current_user
    if user.last_checkin_date == today:
        return jsonify({"streak": user.streak_count, "already": True})

    if user.last_checkin_date and (today - user.last_checkin_date).days == 1:
        user.streak_count += 1
    elif not user.last_checkin_date or (today - user.last_checkin_date).days > 1:
        user.streak_count = 1

    user.last_checkin_date = today
    user.total_points = (user.total_points or 0) + 3
    check_and_award_badges(user)
    db.session.commit()
    return jsonify({"streak": user.streak_count, "points": user.total_points})


@app.route("/tag-cloud")
def tag_cloud():
    """JSON endpoint for tag cloud."""
    tags = get_all_tags()
    posts = get_all_posts()
    tag_counts = {}
    for t in tags:
        tag_counts[t] = sum(1 for p in posts if t in p.get("tags", []))
    max_count = max(tag_counts.values()) if tag_counts else 1
    return jsonify([{"name": t, "count": c, "weight": c / max_count}
                    for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])[:30]])


# ── Error Handlers ──────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ── Init ─────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        # Ensure default badges exist
        default_badges = [
            ("first_comment", "初出茅庐", "发表第一条评论", "💬"),
            ("first_post", "笔耕不辍", "发表第一篇文章", "✍️"),
            ("ten_likes", "人气之星", "累计获得10个赞", "❤️"),
            ("seven_day_streak", "坚持不懈", "连续7天打卡", "🔥"),
            ("fifty_points", "社区达人", "累计获得50积分", "🏆"),
        ]
        for key, name, desc, icon in default_badges:
            if not Badge.query.filter_by(key=key).first():
                db.session.add(Badge(key=key, name=name, description=desc, icon=icon))
        db.session.commit()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
