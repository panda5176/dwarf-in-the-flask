from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_paginate import Pagination, get_page_args
from markdown import markdown
from werkzeug.exceptions import abort

from .auth import login_required
from .db import get_conn, get_cur

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    per_page = 5
    page, _, offset = get_page_args(per_page=per_page)

    cur = get_cur()
    cur.execute("SELECT COUNT(*) FROM posts;")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        f" ORDER BY created DESC;"
    )
    posts = cur.fetchall()

    return render_template(
        "blog/index.html",
        posts=posts,
        pagination=Pagination(page=page, total=total, per_page=per_page),
        search=True,
        bs_version=5,
    )


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "INSERT INTO posts (title, body, author_id)"
                " VALUES (%s, %s, %s);",
                (title, body, g.user["id"]),
            )
            conn.commit()
            return redirect(url_for("blog.index"))

    return render_template("blog/create.html")


def get_post(id):
    cur = get_cur()
    cur.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s;",
        (id,),
    )
    post = cur.fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    return post


@bp.route("/<int:id>/detail", methods=("GET",))
def detail(id):
    post = get_post(id)
    body = markdown(post["body"], extensions=["nl2br", "tables", "fenced_code"])
    return render_template("blog/detail.html", post=post, body=body)


@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    post = get_post(id)

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"].strip()
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "UPDATE posts SET title = %s, body = %s WHERE id = %s;",
                (title, body, id),
            )
            conn.commit()
            return redirect(url_for("blog.index"))

    return render_template("blog/update.html", post=post)


@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    get_post(id)
    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM posts WHERE id = %s;", (id,))
    conn.commit()
    return redirect(url_for("blog.index"))
