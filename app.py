"""Online Book Management System - Flask Backend."""

import hashlib
import os
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for)

from db import Database, create_connection

app = Flask(__name__)
app.secret_key = 'bookstore-secret-key-2024'

# Database


def get_db() -> Database:
    """Return the request-scoped Database instance."""
    if 'db' not in g:
        conn = create_connection()
        g._db_conn = conn
        g.db = Database(conn)
    return g.db


@app.teardown_appcontext
def close_db(exception):
    conn = g.pop('_db_conn', None)
    if conn is not None:
        conn.close()


# Auth helpers

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            return 'Access denied', 403
        return f(*args, **kwargs)
    return decorated


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Helper

def _error_status(msg: str, default: int = 400) -> int:
    """Map an error message to an HTTP status code."""
    if '不存在' in msg:
        return 404
    return default


# Pages

@app.route('/')
def index():
    db = get_db()
    popular = db.get_popular_books()
    rated = db.get_top_rated_books()
    categories = db.get_all_categories()
    return render_template('index.html', popular=popular, rated=rated,
                           categories=categories)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        db = get_db()
        user = db.get_user_by_credentials(username, password)
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email', '')
        db = get_db()
        if db.get_user_by_username(username):
            return render_template('register.html', error='用户名已存在')
        db.create_user(username, hash_password(password), email)
        return redirect(url_for('login_page'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Book browsing

@app.route('/books')
def books_page():
    db = get_db()
    category_id = request.args.get('category', '')
    keyword = request.args.get('keyword', '')

    books = db.get_books(category_id, keyword)
    categories = db.get_all_categories()
    return render_template('books.html', books=books, categories=categories,
                           current_category=category_id, keyword=keyword)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    db = get_db()
    book = db.get_book(book_id)

    if not book:
        return 'Book not found', 404

    reviews = db.get_book_reviews(book_id)

    can_review = False
    has_reviewed = False
    if 'user_id' in session:
        uid = session['user_id']
        has_borrowed = db.user_has_returned_book(uid, book_id)
        has_reviewed = db.user_has_reviewed(uid, book_id)
        can_review = has_borrowed is not None and has_reviewed is None

    can_reserve = False
    has_reserved = False
    if 'user_id' in session:
        uid = session['user_id']
        has_reserved = db.get_pending_reservation(uid, book_id)
        can_reserve = (book['available_copies'] == 0 and
                       has_reserved is None and
                       book['total_copies'] > 0)

    return render_template('book_detail.html', book=book, reviews=reviews,
                           can_review=can_review, has_reviewed=has_reviewed,
                           can_reserve=can_reserve, has_reserved=has_reserved)


# Borrow / Return

@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    db = get_db()
    ok, msg, due_date = db.borrow_book(session['user_id'], book_id)
    if ok:
        return jsonify({'message': msg, 'due_date': due_date})
    return jsonify({'error': msg}), _error_status(msg)


@app.route('/return/<int:record_id>', methods=['POST'])
@login_required
def return_book(record_id):
    db = get_db()
    ok, msg = db.return_book(record_id, session['user_id'])
    if ok:
        return jsonify({'message': msg})
    return jsonify({'error': msg}), _error_status(msg)


@app.route('/my-borrows')
@login_required
def my_borrows():
    db = get_db()
    records = db.get_user_borrows(session['user_id'])
    return render_template('my_borrows.html', records=records)


# Reservation

@app.route('/reserve/<int:book_id>', methods=['POST'])
@login_required
def reserve_book(book_id):
    db = get_db()
    user_id = session['user_id']

    book = db.get_book(book_id)
    if not book:
        return jsonify({'error': '图书不存在'}), 404
    if book['available_copies'] > 0:
        return jsonify({'error': '图书还有可用副本，可直接借阅'}), 400

    if db.get_pending_reservation(user_id, book_id):
        return jsonify({'error': '您已预约此书'}), 400

    db.create_reservation(user_id, book_id)
    return jsonify({'message': '预约成功，图书可借时会通知您'})


@app.route('/my-reservations')
@login_required
def my_reservations():
    db = get_db()
    reservations = db.get_user_reservations(session['user_id'])
    return render_template('my_reservations.html', reservations=reservations)


# Reviews

@app.route('/review/<int:book_id>', methods=['POST'])
@login_required
def add_review(book_id):
    db = get_db()
    user_id = session['user_id']
    rating = int(request.form['rating'])
    comment = request.form.get('comment', '')

    if not db.user_has_returned_book(user_id, book_id):
        return jsonify({'error': '只有借阅并归还此书后才能评论'}), 403

    if db.user_has_reviewed(user_id, book_id):
        return jsonify({'error': '您已评论过此书'}), 400

    if db.create_review(user_id, book_id, rating, comment):
        return jsonify({'message': '评论发表成功'})
    return jsonify({'error': '您已评论过此书'}), 400


# Admin

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'total_users': db.count_users(),
        'total_books': db.count_books(),
        'total_categories': db.count_categories(),
        'active_borrows': db.count_active_borrows(),
        'pending_reservations': db.count_pending_reservations(),
    }
    overdue = db.get_overdue_borrows()
    return render_template('admin/dashboard.html', stats=stats, overdue=overdue)


@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    users = db.get_all_users()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    try:
        db.delete_user(user_id)
    except Exception as e:
        return str(e), 400
    return redirect(url_for('admin_users'))


@app.route('/admin/books')
@admin_required
def admin_books():
    db = get_db()
    books = db.get_books()
    categories = db.get_all_categories()
    return render_template('admin/books.html', books=books, categories=categories)


@app.route('/admin/books/add', methods=['POST'])
@admin_required
def admin_add_book():
    db = get_db()
    db.create_book(
        title=request.form['title'],
        author=request.form['author'],
        isbn=request.form['isbn'],
        published_date=request.form['published_date'],
        total_copies=int(request.form['total_copies']),
        description=request.form['description'],
        category_id=(int(request.form['category_id'])
                     if request.form.get('category_id') else None),
    )
    return redirect(url_for('admin_books'))


@app.route('/admin/books/<int:book_id>/edit', methods=['POST'])
@admin_required
def admin_edit_book(book_id):
    db = get_db()
    db.update_book(
        book_id=book_id,
        title=request.form['title'],
        author=request.form['author'],
        isbn=request.form['isbn'],
        published_date=request.form['published_date'],
        total_copies=int(request.form['total_copies']),
        description=request.form['description'],
        category_id=(int(request.form['category_id'])
                     if request.form.get('category_id') else None),
    )
    return redirect(url_for('admin_books'))


@app.route('/admin/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def admin_delete_book(book_id):
    db = get_db()
    try:
        db.delete_book(book_id)
    except Exception as e:
        return str(e), 400
    return redirect(url_for('admin_books'))


@app.route('/admin/categories')
@admin_required
def admin_categories():
    db = get_db()
    categories = db.get_all_categories()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    db = get_db()
    db.create_category(request.form['name'], request.form['description'])
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<int:cat_id>/edit', methods=['POST'])
@admin_required
def admin_edit_category(cat_id):
    db = get_db()
    db.update_category(cat_id, request.form['name'], request.form['description'])
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<int:cat_id>/delete', methods=['POST'])
@admin_required
def admin_delete_category(cat_id):
    db = get_db()
    db.delete_category(cat_id)
    return redirect(url_for('admin_categories'))


@app.route('/admin/borrows')
@admin_required
def admin_borrows():
    db = get_db()
    records = db.get_all_borrows()
    return render_template('admin/borrows.html', records=records)


@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    db = get_db()
    reservations = db.get_all_reservations()
    return render_template('admin/reservations.html', reservations=reservations)


@app.route('/admin/borrows/<int:record_id>/force-return', methods=['POST'])
@admin_required
def admin_force_return(record_id):
    db = get_db()
    db.force_return(record_id)
    return redirect(url_for('admin_borrows'))


# API endpoints for AJAX 

@app.route('/api/borrow/<int:book_id>', methods=['POST'])
@login_required
def api_borrow(book_id):
    return borrow_book(book_id)


@app.route('/api/return/<int:record_id>', methods=['POST'])
@login_required
def api_return(record_id):
    return return_book(record_id)


@app.route('/api/reserve/<int:book_id>', methods=['POST'])
@login_required
def api_reserve(book_id):
    return reserve_book(book_id)


@app.route('/api/cancel-reservation/<int:res_id>', methods=['POST'])
@login_required
def api_cancel_reservation(res_id):
    db = get_db()
    db.cancel_reservation(res_id, session['user_id'])
    return jsonify({'message': '预约已取消'})



if __name__ == '__main__':
    try:
        conn = create_connection()
        conn.close()
    except Exception as e:
        print(f'Database connection failed: {e}')
        print('Make sure SQL Server is running and run init_db.py first.')
        exit(1)
    app.run(debug=True, port=5000)
