import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from functools import wraps
from sqlalchemy.orm import relationship
from wtforms import SubmitField
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import smtplib
from forms import CreatePostForm, RegisterForm, CommentForm


EMAIL = "testowy100daysms@gmail.com"
PASSWORD = 'REMOVED'

app = Flask(__name__)

# Connect to Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", 'sqlite:///blog.db')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
ckeditor = CKEditor(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)
Bootstrap(app)
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment_author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(current_user)
        if not current_user.is_authenticated:
            return abort(403)
        elif current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def home():
    post_objects = db.session.query(BlogPost).all()
    return render_template("index.html", posts=post_objects)


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = RegisterForm()
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        if not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))
    return render_template("login.html", form=form)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        email = request.form.get('email')
        user = db.session.query(User).filter_by(email=email).first()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        name = request.form.get('name')

        new_user = User()
        new_user.name = name
        new_user.email = email
        new_user.password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256', salt_length=8)

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('home'))

    return render_template("register.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/post/<int:num>", methods=["GET", "POST"])
def get_post(num):
    chosen_post = db.session.query(BlogPost).get(num)
    comment_form = CommentForm()
    if comment_form.is_submitted():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
        new_comment = Comment(
            comment_author_id=current_user.id,
            post_id=chosen_post.id,
            text=comment_form.body.data
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=chosen_post, comment_form=comment_form, current_user=current_user)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    if request.method == "POST":
        new_post = BlogPost(
            title=request.form["title"],
            subtitle=request.form['subtitle'],
            img_url=request.form['img_url'],
            body=request.form['body'],
            date=datetime.now().strftime('%Y-%m-%d'),
            author_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('home'))

    CreatePostForm.submit = SubmitField("Submit Post")
    form = CreatePostForm()
    return render_template('make_post.html', form=form)


@app.route("/edit-post/<post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    CreatePostForm.submit = SubmitField("Confirm Edit Post")
    post = db.session.query(BlogPost).get(post_id)
    form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.img_url = form.img_url.data
        post.body = form.body.data
        db.session.commit()
        return redirect(url_for('get_post', num=post.id))
    return render_template("make_post.html", form=form, is_edit=True)


@app.route("/delete-post/<post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.session.query(BlogPost).get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/delete-comment/<comment_id>")
@admin_only
def delete_comment(comment_id):
    comment_to_delete = db.session.query(Comment).get(comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('get_post', num=comment_to_delete.post_id))


@app.route("/about")
def get_about_page():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def get_contact_page():
    if request.method == "POST":
        data = request.form
        send_mail(data)
        return render_template("contact.html", if_correct=True)
    return render_template("contact.html", if_correct=False)


def send_mail(data):
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(user=EMAIL, password=PASSWORD)
        connection.sendmail(
            from_addr=EMAIL,
            to_addrs="testowy100daysms@gmail.com",
            msg=f"Subject:New mail from {data['name']}!\n\n"
                f"Name: {data['name']}\n"
                f"Email: {data['email']}\n"
                f"Phone: {data['phone']}\n"
                f"Message: {data['message']}")


if __name__ == "__main__":
    app.run(debug=True)
