"""Database models for the social blog."""
from datetime import datetime, timezone, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ── User ─────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # nullable for OAuth
    avatar_url = db.Column(db.String(500))
    bio = db.Column(db.String(280))
    website = db.Column(db.String(200))
    github_username = db.Column(db.String(80))
    twitter_username = db.Column(db.String(80))
    github_id = db.Column(db.String(40), unique=True)  # OAuth
    streak_count = db.Column(db.Integer, default=0)
    last_checkin_date = db.Column(db.Date)
    total_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    comments = db.relationship("Comment", backref="author", lazy="dynamic",
                               foreign_keys="Comment.user_id")
    likes = db.relationship("Reaction", backref="user", lazy="dynamic")
    favorites = db.relationship("Favorite", backref="user", lazy="dynamic")
    followers = db.relationship("Follow", foreign_keys="Follow.following_id",
                                backref="following_user", lazy="dynamic")
    following = db.relationship("Follow", foreign_keys="Follow.follower_id",
                                backref="follower_user", lazy="dynamic")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic",
                                   foreign_keys="Notification.user_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def avatar(self):
        if self.avatar_url:
            return self.avatar_url
        import hashlib
        return f"https://www.gravatar.com/avatar/{hashlib.md5(self.email.lower().encode()).hexdigest()}?d=retro&s=80"

    @property
    def follower_count(self):
        return Follow.query.filter_by(following_id=self.id).count()

    @property
    def following_count(self):
        return Follow.query.filter_by(follower_id=self.id).count()

    @property
    def post_count(self):
        from app import get_all_posts  # lazy import
        # Simple approximation: count likes + comments
        return Reaction.query.filter_by(user_id=self.id).count() + Comment.query.filter_by(user_id=self.id).count()

    def to_dict(self):
        return {
            "id": self.id, "username": self.username,
            "avatar": self.avatar, "bio": self.bio,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "streak_count": self.streak_count,
            "total_points": self.total_points,
        }


# ── Comment (with threading) ────────────────────────────────────────────

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    post_slug = db.Column(db.String(200), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Threading
    parent = db.relationship("Comment", remote_side=[id], backref="replies")

    @property
    def reply_count(self):
        return Comment.query.filter_by(parent_id=self.id).count()


# ── Reactions (multiple types) ──────────────────────────────────────────

class Reaction(db.Model):
    __tablename__ = "reactions"
    id = db.Column(db.Integer, primary_key=True)
    post_slug = db.Column(db.String(200), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reaction_type = db.Column(db.String(10), default="like")  # like, love, clap, wow, fire, think
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("post_slug", "user_id", name="uq_reaction_post_user"),
    )


# ── Favorite ─────────────────────────────────────────────────────────────

class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    post_slug = db.Column(db.String(200), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("post_slug", "user_id", name="uq_fav_post_user"),
    )


# ── Follow ───────────────────────────────────────────────────────────────

class Follow(db.Model):
    __tablename__ = "follows"
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("follower_id", "following_id", name="uq_follow"),
    )


# ── Notification ─────────────────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notif_type = db.Column(db.String(30), nullable=False)  # comment, reply, like, follow, mention
    post_slug = db.Column(db.String(200))
    comment_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    actor = db.relationship("User", foreign_keys=[actor_id])


# ── Badge / Achievement ──────────────────────────────────────────────────

class Badge(db.Model):
    __tablename__ = "badges"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(10))  # emoji


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    badge = db.relationship("Badge")


# ── Pinned Posts ─────────────────────────────────────────────────────────

class PinnedPost(db.Model):
    __tablename__ = "pinned_posts"
    id = db.Column(db.Integer, primary_key=True)
    post_slug = db.Column(db.String(200), unique=True, nullable=False)
    pinned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
