"""Online Book Management System - Flask Backend."""

import hashlib
import os
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for)

app = Flask(__name__)
app.secret_key = 'bookstore-secret-key-2024'

# ── Database ────────────────────────────────────────────────────────────────
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bookstore.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Auth helpers ────────────────────────────────────────────────────────────

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


# ── Pages ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    # Top 5 popular books by borrow count
    popular = db.execute("""
        SELECT b.book_id, b.title, b.author, COUNT(br.record_id) AS borrow_count
        FROM book b
        LEFT JOIN borrow_record br ON b.book_id = br.book_id
        GROUP BY b.book_id, b.title, b.author
        ORDER BY borrow_count DESC
        LIMIT 5
    """).fetchall()

    # Books with ratings
    rated = db.execute("""
        SELECT * FROM view_book_rating
        ORDER BY avg_rating DESC
        LIMIT 6
    """).fetchall()

    categories = db.execute('SELECT * FROM category ORDER BY category_id').fetchall()
    return render_template('index.html', popular=popular, rated=rated, categories=categories)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        db = get_db()
        user = db.execute(
            'SELECT * FROM user WHERE username = ? AND password = ?',
            (username, password)).fetchone()
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
        existing = db.execute(
            'SELECT user_id FROM user WHERE username = ?', (username,)).fetchone()
        if existing:
            return render_template('register.html', error='用户名已存在')
        db.execute(
            'INSERT INTO user (username, password, email, role) VALUES (?,?,?,"reader")',
            (username, hash_password(password), email))
        db.commit()
        return redirect(url_for('login_page'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ── Book browsing ───────────────────────────────────────────────────────────

@app.route('/books')
def books_page():
    db = get_db()
    category_id = request.args.get('category', '')
    keyword = request.args.get('keyword', '')

    query = """
        SELECT b.*, c.name AS category_name,
               COALESCE(vr.avg_rating, 0) AS avg_rating,
               COALESCE(vr.review_count, 0) AS review_count
        FROM book b
        LEFT JOIN category c ON b.category_id = c.category_id
        LEFT JOIN view_book_rating vr ON b.book_id = vr.book_id
        WHERE 1=1
    """
    params = []

    if category_id:
        query += ' AND b.category_id = ?'
        params.append(category_id)
    if keyword:
        query += ' AND (b.title LIKE ? OR b.author LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    query += ' ORDER BY b.book_id DESC'

    books = db.execute(query, params).fetchall()
    categories = db.execute('SELECT * FROM category ORDER BY category_id').fetchall()
    return render_template('books.html', books=books, categories=categories,
                           current_category=category_id, keyword=keyword)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    db = get_db()
    book = db.execute("""
        SELECT b.*, c.name AS category_name,
               COALESCE(vr.avg_rating, 0) AS avg_rating,
               COALESCE(vr.review_count, 0) AS review_count
        FROM book b
        LEFT JOIN category c ON b.category_id = c.category_id
        LEFT JOIN view_book_rating vr ON b.book_id = vr.book_id
        WHERE b.book_id = ?
    """, (book_id,)).fetchone()

    if not book:
        return 'Book not found', 404

    reviews = db.execute("""
        SELECT r.*, u.username
        FROM review r
        JOIN user u ON r.user_id = u.user_id
        WHERE r.book_id = ?
        ORDER BY r.created_at DESC
    """, (book_id,)).fetchall()

    # Check if current user can review (has borrowed and returned this book)
    can_review = False
    has_reviewed = False
    if 'user_id' in session:
        uid = session['user_id']
        has_borrowed = db.execute("""
            SELECT record_id FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND status = '已还'
        """, (uid, book_id)).fetchone()
        has_reviewed = db.execute("""
            SELECT review_id FROM review WHERE user_id = ? AND book_id = ?
        """, (uid, book_id)).fetchone()
        can_review = has_borrowed is not None and has_reviewed is None

    # Check if user can reserve
    can_reserve = False
    has_reserved = False
    if 'user_id' in session:
        uid = session['user_id']
        has_reserved = db.execute("""
            SELECT reservation_id FROM reservation
            WHERE user_id = ? AND book_id = ? AND status = '待处理'
        """, (uid, book_id)).fetchone()
        can_reserve = (book['available_copies'] == 0 and
                       has_reserved is None and
                       book['total_copies'] > 0)

    return render_template('book_detail.html', book=book, reviews=reviews,
                           can_review=can_review, has_reviewed=has_reviewed,
                           can_reserve=can_reserve, has_reserved=has_reserved)


# ── Borrow / Return ─────────────────────────────────────────────────────────
# sp_borrow_book — stored procedure emulated as Python function with transaction

@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    db = get_db()
    user_id = session['user_id']
    due_date = date.today() + timedelta(days=30)

    # Check if user already has this book borrowed
    existing = db.execute("""
        SELECT record_id FROM borrow_record
        WHERE user_id = ? AND book_id = ? AND status = '借出'
    """, (user_id, book_id)).fetchone()
    if existing:
        return jsonify({'error': '您已借阅此书，不可重复借阅'}), 400

    try:
        db.execute('BEGIN EXCLUSIVE TRANSACTION')

        # Lock book row and check availability
        book = db.execute(
            'SELECT available_copies FROM book WHERE book_id = ?',
            (book_id,)).fetchone()
        if not book:
            db.execute('ROLLBACK')
            return jsonify({'error': '图书不存在'}), 404

        avail = book['available_copies']
        if avail > 0:
            db.execute("""
                INSERT INTO borrow_record (user_id, book_id, borrow_date, due_date, status)
                VALUES (?, ?, ?, ?, '借出')
            """, (user_id, book_id, date.today().isoformat(), due_date.isoformat()))
            db.execute(
                'UPDATE book SET available_copies = available_copies - 1 WHERE book_id = ?',
                (book_id,))
            db.execute('COMMIT')
            return jsonify({'message': '借阅成功', 'due_date': due_date.isoformat()})
        else:
            db.execute('ROLLBACK')
            return jsonify({'error': '图书无可用副本，您可以预约此书'}), 400
    except Exception as e:
        db.execute('ROLLBACK')
        return jsonify({'error': str(e)}), 500


# sp_return_book — stored procedure emulated as Python function

@app.route('/return/<int:record_id>', methods=['POST'])
@login_required
def return_book(record_id):
    db = get_db()
    user_id = session['user_id']

    record = db.execute(
        'SELECT * FROM borrow_record WHERE record_id = ? AND user_id = ?',
        (record_id, user_id)).fetchone()
    if not record:
        return jsonify({'error': '借阅记录不存在'}), 404
    if record['status'] == '已还':
        return jsonify({'error': '此书已归还'}), 400

    try:
        db.execute('BEGIN EXCLUSIVE TRANSACTION')

        # Update borrow record
        db.execute("""
            UPDATE borrow_record
            SET return_date = ?, status = '已还'
            WHERE record_id = ?
        """, (date.today().isoformat(), record_id))

        # Restore available copies
        db.execute(
            'UPDATE book SET available_copies = available_copies + 1 WHERE book_id = ?',
            (record['book_id'],))

        db.execute('COMMIT')

        # trg_after_return: Check reservations and notify
        reservation = db.execute("""
            SELECT * FROM reservation
            WHERE book_id = ? AND status = '待处理'
            ORDER BY reserve_date ASC
            LIMIT 1
        """, (record['book_id'],)).fetchone()

        msg = '归还成功'
        if reservation:
            db.execute(
                "UPDATE reservation SET status = '可借' WHERE reservation_id = ?",
                (reservation['reservation_id'],))
            db.commit()
            msg += '，已有预约用户可借阅此书'

        return jsonify({'message': msg})
    except Exception as e:
        db.execute('ROLLBACK')
        return jsonify({'error': str(e)}), 500


@app.route('/my-borrows')
@login_required
def my_borrows():
    db = get_db()
    records = db.execute("""
        SELECT br.*, b.title, b.author,
               CASE WHEN br.return_date IS NULL AND br.due_date < DATE('now')
                    THEN '逾期' ELSE br.status END AS current_status
        FROM borrow_record br
        JOIN book b ON br.book_id = b.book_id
        WHERE br.user_id = ?
        ORDER BY br.borrow_date DESC
    """, (session['user_id'],)).fetchall()
    return render_template('my_borrows.html', records=records)


# ── Reservation ─────────────────────────────────────────────────────────────

@app.route('/reserve/<int:book_id>', methods=['POST'])
@login_required
def reserve_book(book_id):
    db = get_db()
    user_id = session['user_id']

    # Check if book exists and is unavailable
    book = db.execute('SELECT * FROM book WHERE book_id = ?', (book_id,)).fetchone()
    if not book:
        return jsonify({'error': '图书不存在'}), 404
    if book['available_copies'] > 0:
        return jsonify({'error': '图书还有可用副本，可直接借阅'}), 400

    # Check duplicate reservation
    existing = db.execute("""
        SELECT reservation_id FROM reservation
        WHERE user_id = ? AND book_id = ? AND status = '待处理'
    """, (user_id, book_id)).fetchone()
    if existing:
        return jsonify({'error': '您已预约此书'}), 400

    db.execute("""
        INSERT INTO reservation (user_id, book_id, reserve_date, status)
        VALUES (?, ?, datetime('now', 'localtime'), '待处理')
    """, (user_id, book_id))
    db.commit()
    return jsonify({'message': '预约成功，图书可借时会通知您'})


@app.route('/my-reservations')
@login_required
def my_reservations():
    db = get_db()
    reservations = db.execute("""
        SELECT r.*, b.title, b.author
        FROM reservation r
        JOIN book b ON r.book_id = b.book_id
        WHERE r.user_id = ?
        ORDER BY r.reserve_date DESC
    """, (session['user_id'],)).fetchall()
    return render_template('my_reservations.html', reservations=reservations)


# ── Reviews ─────────────────────────────────────────────────────────────────
# trg_prevent_duplicate_review emulated here

@app.route('/review/<int:book_id>', methods=['POST'])
@login_required
def add_review(book_id):
    db = get_db()
    user_id = session['user_id']
    rating = int(request.form['rating'])
    comment = request.form.get('comment', '')

    # Check: user must have borrowed AND returned this book
    has_returned = db.execute("""
        SELECT record_id FROM borrow_record
        WHERE user_id = ? AND book_id = ? AND status = '已还'
    """, (user_id, book_id)).fetchone()
    if not has_returned:
        return jsonify({'error': '只有借阅并归还此书后才能评论'}), 403

    # Check: no duplicate review (enforced by UNIQUE constraint too)
    existing = db.execute(
        'SELECT review_id FROM review WHERE user_id = ? AND book_id = ?',
        (user_id, book_id)).fetchone()
    if existing:
        return jsonify({'error': '您已评论过此书'}), 400

    try:
        db.execute("""
            INSERT INTO review (user_id, book_id, rating, comment)
            VALUES (?, ?, ?, ?)
        """, (user_id, book_id, rating, comment))
        db.commit()
        return jsonify({'message': '评论发表成功'})
    except sqlite3.IntegrityError:
        return jsonify({'error': '您已评论过此书'}), 400


# ── Admin ───────────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'total_users': db.execute('SELECT COUNT(*) FROM user').fetchone()[0],
        'total_books': db.execute('SELECT COUNT(*) FROM book').fetchone()[0],
        'total_categories': db.execute('SELECT COUNT(*) FROM category').fetchone()[0],
        'active_borrows': db.execute(
            "SELECT COUNT(*) FROM borrow_record WHERE status = '借出'").fetchone()[0],
        'pending_reservations': db.execute(
            "SELECT COUNT(*) FROM reservation WHERE status = '待处理'").fetchone()[0],
    }
    # Overdue records
    overdue = db.execute("""
        SELECT u.username, u.email, b.title, br.borrow_date, br.due_date,
               CAST(julianday('now') - julianday(br.due_date) AS INTEGER) AS overdue_days
        FROM borrow_record br
        JOIN user u ON br.user_id = u.user_id
        JOIN book b ON br.book_id = b.book_id
        WHERE br.status = '借出' AND br.due_date < DATE('now')
        ORDER BY overdue_days DESC
    """).fetchall()

    return render_template('admin/dashboard.html', stats=stats, overdue=overdue)


@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    users = db.execute('SELECT * FROM user ORDER BY created_at DESC').fetchall()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    db.execute('DELETE FROM user WHERE user_id = ? AND role != "admin"', (user_id,))
    db.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/books')
@admin_required
def admin_books():
    db = get_db()
    books = db.execute("""
        SELECT b.*, c.name AS category_name
        FROM book b
        LEFT JOIN category c ON b.category_id = c.category_id
        ORDER BY b.book_id DESC
    """).fetchall()
    categories = db.execute('SELECT * FROM category ORDER BY category_id').fetchall()
    return render_template('admin/books.html', books=books, categories=categories)


@app.route('/admin/books/add', methods=['POST'])
@admin_required
def admin_add_book():
    db = get_db()
    db.execute("""
        INSERT INTO book (title, author, isbn, published_date, total_copies,
                          available_copies, description, category_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form['title'],
        request.form['author'],
        request.form['isbn'],
        request.form['published_date'],
        int(request.form['total_copies']),
        int(request.form['total_copies']),
        request.form['description'],
        int(request.form['category_id']) if request.form.get('category_id') else None,
    ))
    db.commit()
    return redirect(url_for('admin_books'))


@app.route('/admin/books/<int:book_id>/edit', methods=['POST'])
@admin_required
def admin_edit_book(book_id):
    db = get_db()
    db.execute("""
        UPDATE book SET title=?, author=?, isbn=?, published_date=?,
        total_copies=?, description=?, category_id=?
        WHERE book_id=?
    """, (
        request.form['title'],
        request.form['author'],
        request.form['isbn'],
        request.form['published_date'],
        int(request.form['total_copies']),
        request.form['description'],
        int(request.form['category_id']) if request.form.get('category_id') else None,
        book_id,
    ))
    db.commit()
    return redirect(url_for('admin_books'))


@app.route('/admin/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def admin_delete_book(book_id):
    db = get_db()
    db.execute('DELETE FROM book WHERE book_id = ?', (book_id,))
    db.commit()
    return redirect(url_for('admin_books'))


@app.route('/admin/categories')
@admin_required
def admin_categories():
    db = get_db()
    categories = db.execute('SELECT * FROM category ORDER BY category_id').fetchall()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    db = get_db()
    db.execute('INSERT INTO category (name, description) VALUES (?, ?)',
               (request.form['name'], request.form['description']))
    db.commit()
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<int:cat_id>/edit', methods=['POST'])
@admin_required
def admin_edit_category(cat_id):
    db = get_db()
    db.execute('UPDATE category SET name=?, description=? WHERE category_id=?',
               (request.form['name'], request.form['description'], cat_id))
    db.commit()
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<int:cat_id>/delete', methods=['POST'])
@admin_required
def admin_delete_category(cat_id):
    db = get_db()
    db.execute('DELETE FROM category WHERE category_id = ?', (cat_id,))
    db.commit()
    return redirect(url_for('admin_categories'))


@app.route('/admin/borrows')
@admin_required
def admin_borrows():
    db = get_db()
    records = db.execute("""
        SELECT br.*, u.username, b.title AS book_title,
               CASE WHEN br.status = '借出' AND br.due_date < DATE('now') THEN 1 ELSE 0 END AS is_overdue
        FROM borrow_record br
        JOIN user u ON br.user_id = u.user_id
        JOIN book b ON br.book_id = b.book_id
        ORDER BY br.borrow_date DESC
    """).fetchall()
    return render_template('admin/borrows.html', records=records)


@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    db = get_db()
    reservations = db.execute("""
        SELECT r.*, u.username, b.title AS book_title
        FROM reservation r
        JOIN user u ON r.user_id = u.user_id
        JOIN book b ON r.book_id = b.book_id
        ORDER BY r.reserve_date DESC
    """).fetchall()
    return render_template('admin/reservations.html', reservations=reservations)


@app.route('/admin/borrows/<int:record_id>/force-return', methods=['POST'])
@admin_required
def admin_force_return(record_id):
    db = get_db()
    record = db.execute(
        'SELECT * FROM borrow_record WHERE record_id = ?', (record_id,)).fetchone()
    if record and record['status'] == '借出':
        db.execute("""
            UPDATE borrow_record
            SET return_date = ?, status = '已还'
            WHERE record_id = ?
        """, (date.today().isoformat(), record_id))
        db.execute(
            'UPDATE book SET available_copies = available_copies + 1 WHERE book_id = ?',
            (record['book_id'],))
        db.commit()
    return redirect(url_for('admin_borrows'))


# ── API endpoints for AJAX ──────────────────────────────────────────────────

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
    db.execute(
        "UPDATE reservation SET status = '已取消' WHERE reservation_id = ? AND user_id = ?",
        (res_id, session['user_id']))
    db.commit()
    return jsonify({'message': '预约已取消'})


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(DB):
        print('Database not found. Run init_db.py first.')
    else:
        app.run(debug=True, port=5000)
