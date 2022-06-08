import os, re
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_paginate import Pagination, get_page_args
from markdown import markdown
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename

from .auth import admin_only, login_required
from .db import get_conn, get_cur

BP = Blueprint("blog", __name__)


def get_all_tags():
    cur = get_cur()
    cur.execute("SELECT * FROM tags ORDER BY title;")
    tags = cur.fetchall()

    return tags


@BP.route("/", methods=("GET", "POST"))
def index():
    per_page = 10
    page, _, offset = get_page_args(per_page=per_page)
    tag_id = request.args.get("tag_id", 0)

    cur = get_cur()
    if request.method == "POST":
        query = request.form["query"].replace("<script>", "&lt;script&gt;")
        query_for_like = ("%" + query + "%").lower()
        cur.execute(
            "SELECT COUNT(*) FROM posts "
            "WHERE (LOWER(title) LIKE %s) OR (LOWER(body) LIKE %s);",
            (query_for_like, query_for_like),
        )
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT p.id, title, body, created, modified, author_id, views, "
            "username "
            "FROM posts p JOIN users u ON p.author_id = u.id "
            "WHERE (LOWER(title) LIKE %s) OR (LOWER(body) LIKE %s) "
            "ORDER BY created DESC LIMIT %s OFFSET %s;",
            (query_for_like, query_for_like, per_page, offset),
        )
    elif tag_id:
        cur.execute(
            "SELECT COUNT(*) FROM posts p "
            "JOIN post2tag pt ON p.id = pt.post_id WHERE pt.tag_id = %s;",
            (tag_id,),
        )
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT p.id, title, body, created, modified, author_id, views, "
            "username "
            "FROM posts p JOIN users u ON p.author_id = u.id "
            "JOIN post2tag pt ON p.id = pt.post_id WHERE pt.tag_id = %s "
            "ORDER BY created DESC LIMIT %s OFFSET %s;",
            (tag_id, per_page, offset),
        )
    else:
        cur.execute("SELECT COUNT(*) FROM posts p;")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT p.id, title, body, created, modified, author_id, views, "
            "username "
            "FROM posts p JOIN users u ON p.author_id = u.id "
            "ORDER BY created DESC LIMIT %s OFFSET %s;",
            (per_page, offset),
        )
    posts = cur.fetchall()

    total_comments = list()
    for post in posts:
        cur.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = %s;", (post["id"],)
        )
        total_comments.append(cur.fetchone()[0])

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
        total=total,
        all_tags=all_tags,
        tag_id=int(tag_id),
        total_comments=total_comments,
        zip=zip,
    )


@BP.route("/create", methods=("GET", "POST"))
@admin_only
@login_required
def create():
    all_tags = get_all_tags()

    if request.method == "POST":
        title = request.form["title"].replace("<script>", "&lt;script&gt;")
        body = request.form["body"].replace("<script>", "&lt;script&gt;")
        files = request.files.getlist("file")

        conn = get_conn()
        cur = get_cur()
        cur.execute(
            "INSERT INTO posts (title, body, author_id, views) "
            "VALUES (%s, %s, %s, 0);",
            (title, body, g.user["id"]),
        )
        conn.commit()

        cur.execute("SELECT MAX(id) FROM posts;")
        post_id = cur.fetchone()[0]

        for tag in all_tags:
            if request.form.get(f"tag-{tag['id']}"):
                cur.execute(
                    "INSERT INTO post2tag (post_id, tag_id) VALUES (%s, %s);",
                    (post_id, tag["id"]),
                )

        for file_obj in files:
            if file_obj.filename == str():
                break

            upload_dir = os.path.join(current_app.instance_path, str(post_id))
            if not os.path.isdir(upload_dir):
                os.makedirs(upload_dir)

            file_path = os.path.join(
                upload_dir, secure_filename(file_obj.filename)
            )
            file_obj.save(file_path)
            cur.execute(
                "INSERT INTO files (post_id, file_path) VALUES (%s, %s);",
                (post_id, file_path),
            )

        conn.commit()
        flash("글을 등록했습니다.", "info")
        return redirect(url_for("blog.detail", id=post_id))

    return render_template("blog/create.html", all_tags=all_tags)


def get_post(id):
    cur = get_cur()
    cur.execute(
        "SELECT p.id, author_id, created, modified, title, body, views, "
        "username FROM posts p JOIN users u ON p.author_id = u.id "
        "WHERE p.id = %s;",
        (id,),
    )
    post = cur.fetchone()

    if post is None:
        abort(404)

    return post


def get_tags_from_post_id(post_id):
    cur = get_cur()
    cur.execute(
        "SELECT t.id, title FROM post2tag pt JOIN tags t ON pt.tag_id = t.id "
        "WHERE post_id = %s ORDER BY title;",
        (post_id,),
    )
    tags = cur.fetchall()

    if tags is None:
        abort(404)

    return tags


def get_files_from_post_id(post_id):
    cur = get_cur()
    cur.execute(
        "SELECT id, file_path FROM files WHERE post_id = %s;", (post_id,)
    )
    files = cur.fetchall()

    return files


def get_comments_from_post_id(post_id):
    cur = get_cur()
    cur.execute(
        "SELECT c.id, author_id, created, modified, body, username "
        "FROM comments c JOIN users u ON c.author_id = u.id "
        "WHERE post_id = %s ORDER BY created;",
        (post_id,),
    )
    comments = cur.fetchall()

    if comments is None:
        abort(404)

    return comments


@BP.route("/<int:id>", methods=("GET",))
def detail(id):
    post = get_post(id)
    tags = get_tags_from_post_id(id)
    files = get_files_from_post_id(id)
    comments = get_comments_from_post_id(id)
    body = markdown(post["body"], extensions=["nl2br", "tables", "fenced_code"])

    for file_record in files:
        file_name = os.path.basename(file_record["file_path"])
        file_id = file_record["id"]
        body = re.sub(f'src="{file_name}"', f'src="{id}/{file_id}"', body)

    conn = get_conn()
    cur = get_cur()
    cur.execute(
        "UPDATE posts SET views = %s WHERE id = %s;", (post["views"] + 1, id),
    )
    conn.commit()

    return render_template(
        "blog/detail.html", post=post, body=body, tags=tags, comments=comments
    )


@BP.route("/<int:id>/<int:file_id>", methods=("GET",))
def detail_file(id, file_id):
    cur = get_cur()
    cur.execute("SELECT file_path FROM files WHERE id = %s;", (file_id,))
    file_record = cur.fetchone()

    if file_record is None:
        abort(404)

    file_path = file_record["file_path"]

    return send_file(file_path, download_name=os.path.basename(file_path))


@BP.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    post = get_post(id)
    if post["author_id"] != g.user["id"]:
        abort(403)

    tag_ids = [tag["id"] for tag in get_tags_from_post_id(id)]
    file_ids = [
        os.path.basename(file_record["file_path"])
        for file_record in get_files_from_post_id(id)
    ]
    all_tags = get_all_tags()

    if request.method == "POST":
        title = request.form["title"].replace("<script>", "&lt;script&gt;")
        body = request.form["body"].replace("<script>", "&lt;script&gt;")
        files = request.files.getlist("file")

        conn = get_conn()
        cur = get_cur()
        cur.execute(
            "UPDATE posts SET title = %s, body = %s, "
            "modified = CURRENT_TIMESTAMP WHERE id = %s;",
            (title, body, id),
        )

        for tag in all_tags:
            if request.form.get(f"tag-{tag['id']}"):
                if tag["id"] in tag_ids:
                    continue
                cur.execute(
                    "INSERT INTO post2tag (post_id, tag_id) VALUES (%s, %s);",
                    (id, tag["id"]),
                )
            else:
                cur.execute(
                    "DELETE FROM post2tag WHERE post_id = %s AND tag_id = %s",
                    (id, tag["id"]),
                )

        for file_obj in files:
            if file_obj.filename == str():
                break

            upload_dir = os.path.join(current_app.instance_path, str(id))
            if not os.path.isdir(upload_dir):
                os.makedirs(upload_dir)

            file_path = os.path.join(
                upload_dir, secure_filename(file_obj.filename)
            )
            file_obj.save(file_path)
            cur.execute(
                "INSERT INTO files (post_id, file_path) VALUES (%s, %s);",
                (id, file_path),
            )

        conn.commit()
        flash("글을 수정했습니다.", "info")
        return redirect(url_for("blog.detail", id=id))

    return render_template(
        "blog/update.html",
        post=post,
        tag_ids=tag_ids,
        file_ids=file_ids,
        all_tags=all_tags,
    )


@BP.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    post = get_post(id)
    if post["author_id"] != g.user["id"]:
        abort(403)

    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM post2tag WHERE post_id = %s;", (id,))
    cur.execute("DELETE FROM posts WHERE id = %s;", (id,))
    conn.commit()
    flash("글을 삭제했습니다.", "info")

    return redirect(url_for("blog.index"))


@BP.route("/<int:post_id>/create_comment", methods=("POST",))
@login_required
def create_comment(post_id):
    body = request.form["body"].replace("<script>", "&lt;script&gt;")

    conn = get_conn()
    cur = get_cur()
    cur.execute(
        "INSERT INTO comments (post_id, author_id, body) VALUES (%s, %s, %s);",
        (post_id, g.user["id"], body),
    )
    conn.commit()
    flash("댓글을 등록했습니다.", "info")

    return redirect(url_for("blog.detail", id=post_id, _anchor="comments"))


def get_comment(id):
    cur = get_cur()
    cur.execute(
        "SELECT id, author_id, post_id, created, modified, body "
        "FROM comments WHERE id = %s;",
        (id,),
    )
    comment = cur.fetchone()

    if comment is None:
        abort(404)

    return comment


@BP.route("/<int:post_id>/<int:id>/delete_comment", methods=("POST",))
@login_required
def delete_comment(id, post_id):
    comment = get_comment(id)
    if comment["author_id"] != g.user["id"]:
        abort(403)

    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM comments WHERE id = %s;", (id,))
    conn.commit()
    flash("댓글을 삭제했습니다.", "info")

    return redirect(url_for("blog.detail", id=post_id, _anchor="comments"))

