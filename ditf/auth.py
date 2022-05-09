import functools, re

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_paginate import Pagination, get_page_args
from markdown import markdown
from werkzeug.exceptions import abort
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from .db import get_conn, get_cur

BP = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


def admin_only(view):
    @login_required
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user["id"] != 1:
            abort(403)

        return view(**kwargs)

    return wrapped_view


@BP.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["password-confirm"]
        mail = request.form["mail"]
        error = None

        if password != password_confirm:
            error = "비밀번호를 확인하세요."
        elif re.search("[^\w\!\@\#\$\%\^\&\*]", username):
            error = "아이디는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."
        elif re.search("[^\w\!\@\#\$\%\^\&\*]", password):
            error = "비밀번호는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "SELECT username FROM users WHERE username = %s;", (username,),
            )
            if cur.fetchone():
                flash(f'아이디 "{username}"는 이미 등록되어있습니다.', "warning")
            else:
                cur.execute(
                    "SELECT mail FROM users WHERE mail = %s;", (mail,),
                )

                if cur.fetchone():
                    flash(f'메일 주소 "{mail}"는 이미 등록되어있습니다.', "warning")
                else:
                    cur.execute(
                        "INSERT INTO users (username, password, mail) "
                        "VALUES (%s, %s, %s);",
                        (username, generate_password_hash(password), mail,),
                    )
                    conn.commit()
                    flash("가입 성공하였습니다.", "info")
                    return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@BP.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        if re.search("[^\w\!\@\#\$\%\^\&\*]", username):
            error = "아이디는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."
        elif re.search("[^\w\!\@\#\$\%\^\&\*]", password):
            error = "비밀번호는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."

        if error:
            flash(error, "warning")
        else:
            cur = get_cur()
            cur.execute(
                "SELECT id, username, password, mail, about "
                "FROM users WHERE username = %s;",
                (username,),
            )
            user = cur.fetchone()

            if user is None:
                error = "아이디가 없습니다."
            elif not check_password_hash(user["password"], password):
                error = "비밀번호가 틀렸습니다."

            if error:
                flash(error, "warning")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("로그인했습니다.", "info")

                return redirect(url_for("index"))

    return render_template("auth/login.html")


def get_user(id):
    cur = get_cur()
    cur.execute(
        "SELECT id, username, mail, about, password FROM users WHERE id = %s;",
        (id,),
    )
    user = cur.fetchone()

    if user is None:
        abort(404)

    return user


@BP.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = get_user(user_id)


@BP.route("/logout")
def logout():
    session.clear()
    flash("로그아웃했습니다.", "info")

    return redirect(url_for("index"))


@BP.route("/<int:id>", methods=("GET",))
def userinfo(id):
    cur = get_cur()
    user = get_user(id)
    about = markdown(
        user["about"], extensions=["nl2br", "tables", "fenced_code"],
    )

    per_page = 5
    page, _, offset = get_page_args(per_page=per_page)

    cur.execute("SELECT COUNT(*) FROM posts WHERE author_id = %s;", (id,))
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, title, body, created, modified, author_id, views "
        "FROM posts WHERE author_id = %s ORDER BY created DESC "
        "LIMIT %s OFFSET %s;",
        (id, per_page, offset),
    )
    posts = cur.fetchall()

    return render_template(
        "auth/userinfo.html",
        user=user,
        about=about,
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
    )


@BP.route("/<int:id>/update", methods=("GET", "POST"))
def update(id):
    cur = get_cur()
    user = get_user(id)
    if user["id"] != g.user["id"]:
        abort(403)

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["password-confirm"]
        mail = request.form["mail"]
        about = request.form["about"]
        error = None

        if re.search("[^\w\!\@\#\$\%\^\&\*]", username):
            error = "아이디는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."
        elif re.search("[^\w\!\@\#\$\%\^\&\*]", password):
            error = "비밀번호는 영문 알파벳과 숫자, 그리고 일부 특수문자(_,!,@,#,$,%,^,&,*)만 가능합니다."

        if password:
            if not password_confirm:
                error = "비밀번호 확인이 필요합니다."
            elif password != password_confirm:
                error = "비밀번호를 확인하세요."

        about = about.replace("<script>", "&lt;script&gt;")

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur.execute(
                "SELECT username FROM users WHERE username = %s;", (username,),
            )
            new_user = cur.fetchone()
            if new_user and new_user[0] != user["username"]:
                flash(f'아이디 "{username}"는 이미 등록되어있습니다.', "warning")
            else:
                cur.execute(
                    "SELECT mail FROM users WHERE mail = %s;", (mail,),
                )
                new_mail = cur.fetchone()

                if new_mail and new_mail[0] != user["mail"]:
                    flash(f'메일 주소 "{mail}"는 이미 등록되어있습니다.', "warning")
                else:
                    if password:
                        cur.execute(
                            "UPDATE users SET username = %s, password = %s, "
                            "mail = %s, about = %s WHERE id = %s;",
                            (
                                username,
                                generate_password_hash(password),
                                mail,
                                about,
                                id,
                            ),
                        )
                    else:
                        cur.execute(
                            "UPDATE users SET username = %s, password = %s, "
                            "mail = %s, about = %s WHERE id = %s;",
                            (username, user["password"], mail, about, id,),
                        )
                    conn.commit()
                    flash("사용자 정보를 수정했습니다.", "info")
                    return redirect(url_for("auth.userinfo", id=id))

    return render_template("auth/update.html", user=user)
