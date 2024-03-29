from flask import Blueprint, flash, redirect, render_template, url_for
from flask_paginate import Pagination, get_page_args

from .auth import admin_only
from .db import get_conn, get_cur

BP = Blueprint("admin", __name__, url_prefix="/admin")


@BP.route("/", methods=("GET",))
@admin_only
def view_users():
    per_page = 20
    page, _, offset = get_page_args(per_page=per_page)

    cur = get_cur()
    cur.execute("SELECT COUNT(*) FROM users;")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, username, mail FROM users ORDER BY id "
        "DESC LIMIT %s OFFSET %s;",
        (per_page, offset),
    )
    users = cur.fetchall()

    return render_template(
        "admin/users.html",
        users=users,
        total=total,
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
    )


@BP.route("/<int:id>/delete", methods=("POST",))
@admin_only
def delete_user(id):
    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM users WHERE id = %s;", (id,))
    conn.commit()
    flash("사용자를 삭제했습니다.", "info")

    return redirect(url_for("admin.view_users"))


@BP.route("/comments", methods=("GET",))
@admin_only
def view_comments():
    per_page = 10
    page, _, offset = get_page_args(per_page=per_page)

    cur = get_cur()
    cur.execute("SELECT COUNT(*) FROM comments;")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT c.id, username, post_id, body "
        "FROM comments c JOIN users u ON c.author_id = u.id "
        "ORDER BY modified DESC LIMIT %s OFFSET %s;",
        (per_page, offset),
    )
    comments = cur.fetchall()

    return render_template(
        "admin/comments.html",
        comments=comments,
        total=total,
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
    )


@BP.route("/comments/<int:id>/delete", methods=("POST",))
@admin_only
def delete_comment(id):
    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM comments WHERE id = %s;", (id,))
    conn.commit()
    flash("댓글을 삭제했습니다.", "info")

    return redirect(url_for("admin.view_comments"))

