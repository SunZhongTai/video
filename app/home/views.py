from . import home
from flask import Flask, render_template, redirect, url_for, flash, session, request, Response
from app.home.forms import RegistForm, LoginForm, UserDetailForm, PwdForm, CommentForm
from app.models import User, Userlog, Comment, Movie, Preview, Tag, Moviecol
from werkzeug.security import generate_password_hash
import uuid
from app import db, app, rd
from functools import wraps
from werkzeug.utils import secure_filename  # 文件上传
import os, datetime


# 修改文件名称
def change_filename(filename):  # 需要将filename转换为安全的文件爱你名称（filename）有时间前缀字符串拼接的名称
    file_info = os.path.splitext(filename)  # 分割成后缀加前缀
    filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + str(uuid.uuid4().hex) + file_info[-1]
    return filename


# 定义访问装饰器
def user_login_req(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):  # 定义装饰器的方法
        if "user" not in session:
            return redirect(url_for("home.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# 会员登录
@home.route("/login/", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        data = form.data
        user = User.query.filter_by(name=data["name"]).first()
        if not user.check_pwd(data["pwd"]):
            flash("密码错误！", "err")
            return redirect(url_for("home.login"))
        session["user"] = user.name
        session["user_id"] = user.id
        userlog = Userlog(
            user_id=user.id,
            ip=request.remote_addr
        )
        db.session.add(userlog)
        db.session.commit()
        return redirect(url_for("home.user"))
    return render_template("home/login.html", form=form)


# 会员退出
@home.route("/logout/")
def logout():
    session.pop("user", None)
    session.pop("user_id", None)
    return redirect(url_for("home.login"))


# 会员注册
@home.route("/regist/", methods=['GET', 'POST'])
def register():
    form = RegistForm()
    if form.validate_on_submit():
        data = form.data
        user = User(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            pwd=generate_password_hash(data["pwd"]),
            uuid=uuid.uuid4().hex
        )
        print(user)
        db.session.add(user)
        db.session.commit()
        flash("注册成功", "ok")
    return render_template("home/register.html", form=form)


# 修改会员资料
@home.route("/user/", methods=["GET", "POST"])
@user_login_req
def user():
    form = UserDetailForm()
    user = User.query.get(int(session["user_id"]))
    form.face.validators = []  # 第一次上传头像可以用来空
    # print(user.name)
    if request.method == "GET":
        print(user.name)
        form.name.data = user.name
        form.email.data = user.email
        form.phone.data = user.phone
        form.info.data = user.info
    if form.validate_on_submit():
        data = form.data
        file_face = secure_filename(form.face.data.filename)
        if not os.path.exists(app.config["FC_DIR"]):
            os.makedirs(app.config["FC_DIR"])
            os.chmod(app.config["FC_DIR"], "rw")
        user.face = change_filename(file_face)
        form.face.data.save(app.config["FC_DIR"] + user.face)

        name_count = User.query.filter_by(name=data["name"]).count()
        if name_count == 1 and data["name"] != user.name:
            flash("昵称已经存在！", "ok")
            return redirect(url_for("home.user"))

        email_count = User.query.filter_by(email=data["email"]).count()
        if email_count == 1 and data["email"] != user.email:
            flash("邮箱已经存在！", "ok")
            return redirect(url_for("home.user"))

        phone_count = User.query.filter_by(phone=data["phone"]).count()
        if phone_count == 1 and data["phone"] != user.phone:
            flash("手机号码已经存在！", "ok")
            return redirect(url_for("home.user"))

        user.name = data["name"]
        user.email = data["email"]
        user.phone = data["phone"]
        user.info = data["info"]
        db.session.add(user)
        db.session.commit()
        flash("修改成功", "ok")
        return redirect(url_for("home.user"))
    return render_template("home/user.html", form=form, user=user)


# 修改密码
@home.route("/pwd/", methods=["GET", "POST"])
@user_login_req
def pwd():
    form = PwdForm()
    data = form.data
    if form.validate_on_submit():
        user = User.query.filter_by(name=session["user"]).first()
        if not user.check_pwd(data["old_pwd"]):
            flash("旧密码错误！", "err")
            return redirect(url_for('home.pwd'))
        user.pwd = generate_password_hash(data["new_pwd"])
        db.session.add(user)
        db.session.commit()
        flash("密码修改成功,请重新登陆！", "ok")
        return redirect(url_for('home.logout'))
    return render_template("home/pwd.html", form=form)


# 评论列表
@home.route("/comments/<int:page>/", methods=["GET"])
@user_login_req
def per_comments_list(page=None):
    if page is None:
        page = 1
    page_data = Comment.query.join(
        Movie
    ).join(
        User
    ).filter(
        Movie.id == Comment.movie_id,
        User.id == session["user_id"]
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template("home/comments.html", page_data=page_data)


# 会员登陆日志
@home.route("/loginlog/<int:page>", methods=["GET"])
@user_login_req
def loginlog(page=None):
    if page is None:
        page = 1
    page_data = Userlog.query.filter_by(
        user_id=int(session["user_id"])
    ).order_by(
        Userlog.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template("home/loginlog.html", page_data=page_data)


# 添加电影收藏  ajax异步添加电影收藏
@home.route("/moviecol/add/", methods=["GET"])
@user_login_req
def moviecol_add():
    uid = request.args.get("uid", "")
    mid = request.args.get("mid", "")
    moviecol = Moviecol.query.filter_by(
        user_id=int(uid),
        movie_id=int(mid)
    ).count()
    if moviecol == 1:
        data = dict(ok=0)
    if moviecol == 0:
        moviecol = Moviecol(
            user_id=int(uid),
            movie_id=int(mid)
        )
        db.session.add(moviecol)
        db.session.commit()
        data = dict(ok=1)
    import json
    return json.dumps(data)


# 电影收藏
@home.route("/moviecol/<int:page>/")
@user_login_req
def moviecol(page=None):
    if page is None:
        page = 1
    page_data = Moviecol.query.join(
        Movie
    ).join(
        User
    ).filter(
        Movie.id == Moviecol.movie_id,
        User.id == session["user_id"]
    ).order_by(
        Moviecol.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template("home/moviecol.html", page_data=page_data)


# 首页
@home.route("/<int:page>/", methods=["GET"])
def index(page=None):
    tags = Tag.query.all()
    page_data = Movie.query

    # 标签
    tid = request.args.get("tid", 0)
    if int(tid) != 0:
        page_data = page_data.filter_by(tag_id=int(tid))
    # 星级
    star = request.args.get("star", 0)
    if int(star) != 0:
        page_data = page_data.filter_by(star=int(star))
    # 时间
    time = request.args.get("time", 0)
    if int(time) != 0:
        if int(time) == 1:
            page_data = page_data.order_by(
                Movie.addtime.desc()
            )
        else:
            page_data = page_data.order_by(
                Movie.addtime.asc()
            )
    # 播放量
    pm = request.args.get("pm", 0)
    if int(pm) != 0:
        if int(pm) == 1:
            page_data = page_data.order_by(
                Movie.playnum.desc()
            )
        else:
            page_data = page_data.order_by(
                Movie.playnum.asc()
            )
    # 评论量
    cm = request.args.get("cm", 0)
    if int(cm) != 0:
        if int(cm) == 1:
            page_data = page_data.order_by(
                Movie.commentnum.desc()
            )
        else:
            page_data = page_data.order_by(
                Movie.commentnum.asc()
            )

    if page is None:
        page = 1
    page_data = page_data.paginate(page=page, per_page=1)
    p = dict(
        tid=tid,
        star=star,
        time=time,
        pm=pm,
        cm=cm
    )
    return render_template("home/index.html", tags=tags, p=p, page_data=page_data)


# 上映预告
@home.route("/animation/")
def animation():
    data = Preview.query.all()
    return render_template("home/animation.html", data=data)


# 搜索
@home.route("/search/<int:page>/")
def search(page=None):
    if page is None:
        page = 1
    key = request.args.get("key", "")
    movie_count = Movie.query.filter(
        Movie.title.ilike('%' + key + '%')
    ).count()

    page_data = Movie.query.filter(
        Movie.title.ilike('%' + key + '%')  # 模糊匹配
    ).order_by(
        Movie.addtime.desc()
    ).paginate(page=page, per_page=10)
    page_data.key=key
    return render_template("home/search.html", page=page, key=key, page_data=page_data, movie_count=movie_count)


# @home.route("/play/<int:id>/", methods=["GET", "POST"])
# def play(id=None):
#     movie = Movie.query.join(Tag).filter(
#         Tag.id == Movie.tag_id,
#         Movie.id == int(id)
#     ).first_or_404()  # 只需要一条
#     movie.playnum = movie.playnum + 1
#     form = CommentForm()
#     if "user" in session and form.validate_on_submit():
#         data = form.data
#         comment = Comment(
#             content=data["content"],
#             movie_id=movie.id,
#             user_id=session["user_id"]
#         )
#         db.session.add(comment)
#         db.session.commit()
#         movie.commentnum = movie.commentnum + 1
#         flash("添加评论成功！", "ok")
#         return redirect(url_for('home.play', id=movie.id))
#     db.session.add(movie)
#     db.session.commit()
#     return render_template("home/play.html", movie=movie, form=form)

# 播放
@home.route("/play/<int:id>/<int:page>/", methods=['GET', 'POST'])
def play(id=None, page=None):
    movie = Movie.query.join(Tag).filter(
        Tag.id == Movie.tag_id,  # 关联取出电影的Tag
        Movie.id == int(id)
    ).first_or_404()

    if page is None:
        page = 1
    page_data = Comment.query.join(  # join 进行关联表
        Movie
    ).join(
        User
    ).filter(  # filter 过滤条件
        Movie.id == movie.id,
        User.id == Comment.user_id
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=2)

    movie.playnum = movie.playnum + 1
    form = CommentForm()
    if "user" in session and form.validate_on_submit():
        data = form.data
        comment = Comment(
            content=data["content"],
            movie_id=movie.id,
            user_id=session["user_id"]
        )
        db.session.add(comment)
        db.session.commit()
        movie.commentnum = movie.commentnum + 1
        db.session.add(movie)
        db.session.commit()
        flash("添加评论成功！", "ok")
        return redirect(url_for('home.play', id=movie.id, page=1))
    db.session.add(movie)
    db.session.commit()
    return render_template("home/play.html", movie=movie, form=form, page_data=page_data)


# 弹幕播放
@home.route("/video/<int:id>/<int:page>/", methods=['GET', 'POST'])
def video(id=None, page=None):
    movie = Movie.query.join(Tag).filter(
        Tag.id == Movie.tag_id,  # 关联取出电影的Tag
        Movie.id == int(id)
    ).first_or_404()

    if page is None:
        page = 1
    page_data = Comment.query.join(  # join 进行关联表
        Movie
    ).join(
        User
    ).filter(  # filter 过滤条件
        Movie.id == movie.id,
        User.id == Comment.user_id
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=2)

    movie.playnum = movie.playnum + 1
    form = CommentForm()
    if "user" in session and form.validate_on_submit():
        data = form.data
        comment = Comment(
            content=data["content"],
            movie_id=movie.id,
            user_id=session["user_id"]
        )
        db.session.add(comment)
        db.session.commit()
        movie.commentnum = movie.commentnum + 1
        db.session.add(movie)
        db.session.commit()
        flash("添加评论成功！", "ok")
        return redirect(url_for('home.video', id=movie.id, page=1))
    db.session.add(movie)
    db.session.commit()
    return render_template("home/video.html", movie=movie, form=form, page_data=page_data)


# # 处理弹幕消息
# @home.route("/tm/v3/", methods=["GET", "POST"])
# def tm():
#     import json
#     if request.method == "GET":  # 获取弹幕
#         id = request.args.get('id')  # 用id来获取弹幕消息队列，也就是js中danmaku配置的id
#         key = "movie" + str(id)  # 拼接形成键值用于存放在redis队列中
#         if rd.llen(key):
#             msgs = rd.lrange(key, 0, 2999)
#             res = {
#                 "code": 1,
#                 "danmaku": [json.loads(v) for v in msgs]
#             }
#         else:
#             res = {
#                 "code": 1,  # 无内容code为1
#                 "danmaku": []
#             }
#         resp = json.dumps(res)
#     if request.method == "POST":  # 添加弹幕
#         data = json.loads(request.get_data())
#         # print(data)
#         msg = {
#             "__v": 0,
#             "author": data["author"],
#             "time": data["time"],  # 发送弹幕视频播放进度时间
#             "text": data["text"],  # 弹幕内容
#             "color": data["color"],  # 弹幕颜色
#             "type": data['type'],  # 弹幕位置
#             "ip": request.remote_addr,
#             "_id": datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex,
#             "player": [
#                 data["player"]
#             ]
#         }
#         res = {
#             "code": 1,
#             "data": msg
#         }
#         resp = json.dumps(res)
#         rd.lpush("movie"+str(data['player']), json.dumps(msg))  # 将添加的弹幕推入redis的队列中
#     return Response(resp, mimetype='application/json')
#
#

# 处理弹幕消息
@home.route("/tm/v3/", methods=["GET", "POST"])
def tm():
    from flask import Response
    from app import rd
    import json
    import datetime
    import time
    resp = ''
    if request.method == "GET":  # 获取弹幕
        movie_id = request.args.get('id')  # 用id来获取弹幕消息队列，也就是js中danmaku配置的id
        key = "movie{}:barrage".format(movie_id)  # 拼接形成键值用于存放在redis队列中
        if rd.llen(key):
            msgs = rd.lrange(key, 0, 2999)
            tm_data = []
            for msg in msgs:
                msg = json.loads(msg)
                # print(msg)
                tmp_data = [msg['time'], msg['type'], msg['date'], msg['author'], msg['text']]
                tm_data.append(tmp_data)
            # print(tm_data)
            res = {
                "code": 0,
                # 参照官网http://dplayer.js.org/#/ 获取弹幕的消息格式
                # "data": [[6.978, 0, 16777215, "DIYgod", "1111111111111111111"],
                #          [16.338, 0, 16777215, "DIYgod", "测试"],
                #          [8.177, 0, 16777215, "DIYgod", "测试"],
                #          [7.358, 0, 16777215, "DIYgod", "1"],
                #          [15.748338, 0, 16777215, "DIYgod", "owo"]],
                "data": tm_data,
            }
        else:
            print('Redis中暂无内容')
            res = {
                "code": 1,  # 无内容code为1
                "data": []
            }
        resp = json.dumps(res)
    if request.method == "POST":  # 添加弹幕
        data = json.loads(request.get_data())
        # print(data)
        msg = {
            "__v": 0,
            "author": data["author"],
            "time": data["time"],  # 发送弹幕视频播放进度时间
            "date": int(time.time()),  # 当前时间戳
            "text": data["text"],  # 弹幕内容
            "color": data["color"],  # 弹幕颜色
            "type": data['type'],  # 弹幕位置
            "ip": request.remote_addr,
            "_id": datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex,
            "player": data['id']
        }
        res = {
            "code": 0,
            "data": msg
        }
        resp = json.dumps(res)
        rd.lpush("movie{}:barrage".format(data['id']), json.dumps(msg))  # 将添加的弹幕推入redis的队列中
    return Response(resp, mimetype='application/json')
