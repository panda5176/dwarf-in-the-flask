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

from .auth import admin_only, login_required
from .db import get_conn, get_cur

bp = Blueprint("blog", __name__)


def get_all_tags():
    cur = get_cur()
    cur.execute("SELECT * FROM tags;")
    tags = cur.fetchall()
    return tags


@bp.route("/", methods=("GET",))
def index():
    per_page = 5
    page, _, offset = get_page_args(per_page=per_page)
    tag_id = request.args.get("tag_id", 0)

    cur = get_cur()
    cur.execute("SELECT COUNT(*) FROM posts;")
    total = cur.fetchone()[0]
    if tag_id:
        cur.execute(
            "SELECT p.id, title, body, created, modified, author_id, views, "
            "username "
            "FROM posts p JOIN users u ON p.author_id = u.id "
            "JOIN post2tag pt ON p.id = pt.post_id WHERE pt.tag_id = %s "
            "ORDER BY created DESC LIMIT %s OFFSET %s;",
            (tag_id, per_page, offset),
        )
    else:
        cur.execute(
            "SELECT p.id, title, body, created, modified, author_id, views, "
            "username "
            "FROM posts p JOIN users u ON p.author_id = u.id "
            "ORDER BY created DESC LIMIT %s OFFSET %s;",
            (per_page, offset),
        )
    posts = cur.fetchall()

    all_tags = get_all_tags()

    return render_template(
        "blog/index.html",
        posts=posts,
        pagination=Pagination(
            page=page,
            total=total,
            per_page=per_page,
            prev_label="<<",
            next_label=">>",
            format_total=True,
            format_number=True,
        ),
        search=True,
        bs_version=5,
        all_tags=all_tags,
        tag_id=int(tag_id),
    )


@bp.route("/create", methods=("GET", "POST"))
@admin_only
@login_required
def create():
    all_tags = get_all_tags()

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        title = title.replace("<script>", "&lt;script&gt;")
        body = body.replace("<script>", "&lt;script&gt;")

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "INSERT INTO posts (title, body, author_id, views)"
                " VALUES (%s, %s, %s, 0);",
                (title, body, g.user["id"]),
            )

            cur.execute("SELECT MAX(id) FROM posts;")
            post_id = cur.fetchone()[0]

            for tag in all_tags:
                if request.form.get(f"tag-{tag['id']}"):
                    cur.execute(
                        "INSERT INTO post2tag (post_id, tag_id)"
                        " VALUES (%s, %s);",
                        (post_id, tag["id"]),
                    )

            conn.commit()
            flash("The post was successfully created.", "info")
            return redirect(url_for("blog.detail", id=post_id))

    return render_template("blog/create.html", all_tags=all_tags)


def get_post(id):
    cur = get_cur()
    cur.execute(
        "SELECT p.id, author_id, created, modified, title, body, views, "
        "username "
        "FROM posts p JOIN users u ON p.author_id = u.id "
        "WHERE p.id = %s;",
        (id,),
    )
    post = cur.fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    return post


def get_tag_ids_from_post_id(post_id):
    cur = get_cur()
    cur.execute(
        "SELECT tag_id FROM post2tag WHERE post_id = %s;", (post_id,),
    )
    tag_ids = cur.fetchall()

    if tag_ids is None:
        abort(404, f"Post id {post_id} doesn't exist.")

    return tag_ids


def get_tag(id):
    cur = get_cur()
    cur.execute("SELECT id, title FROM tags WHERE id = %s;", (id,))
    tag = cur.fetchone()

    if tag is None:
        abort(404, f"Tag id {id} doesn't exist.")

    return tag


@bp.route("/<int:id>", methods=("GET",))
def detail(id):
    post = get_post(id)
    tags = [get_tag(tag_id[0]) for tag_id in get_tag_ids_from_post_id(id)]
    body = markdown(post["body"], extensions=["nl2br", "tables", "fenced_code"])

    conn = get_conn()
    cur = get_cur()
    cur.execute(
        "UPDATE posts SET views = %s WHERE id = %s;", (post["views"] + 1, id),
    )
    conn.commit()

    return render_template("blog/detail.html", post=post, body=body, tags=tags)


@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    post = get_post(id)
    if post["author_id"] != g.user["id"]:
        flash("Invalid access.", "warning")
        return redirect(url_for("blog.detail", id=id))

    tag_ids = [
        get_tag(tag_id[0])["id"] for tag_id in get_tag_ids_from_post_id(id)
    ]
    all_tags = get_all_tags()

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"].strip()
        error = None

        if not title:
            error = "Title is required."

        title = title.replace("<script>", "&lt;script&gt;")
        body = body.replace("<script>", "&lt;script&gt;")

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "UPDATE posts SET title = %s, body = %s, "
                "modified = CURRENT_TIMESTAMP "
                "WHERE id = %s;",
                (title, body, id),
            )

            for tag in all_tags:
                if request.form.get(f"tag-{tag['id']}"):
                    if tag["id"] in tag_ids:
                        continue
                    cur.execute(
                        "INSERT INTO post2tag (post_id, tag_id)"
                        " VALUES (%s, %s);",
                        (id, tag["id"]),
                    )
                else:
                    cur.execute(
                        "DELETE FROM post2tag "
                        "WHERE post_id = %s AND tag_id = %s",
                        (id, tag["id"]),
                    )

            conn.commit()
            flash("The post was successfully edited.", "info")
            return redirect(url_for("blog.detail", id=id))

    return render_template(
        "blog/update.html", post=post, tag_ids=tag_ids, all_tags=all_tags
    )


@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    post = get_post(id)
    if post["author_id"] != g.user["id"]:
        flash("Invalid access.", "warning")
        return redirect(url_for("blog.detail", id=id))

    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM post2tag WHERE post_id = %s;", (id,))
    cur.execute("DELETE FROM posts WHERE id = %s;", (id,))
    conn.commit()
    flash("The post was successfully deleted.", "info")
    return redirect(url_for("blog.index"))
