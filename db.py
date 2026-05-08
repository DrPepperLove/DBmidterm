"""Database abstraction layer for the Online Book Management System.

Encapsulates all SQLite operations behind a clean API, organized by domain entity.
"""

import sqlite3
from datetime import date, timedelta


class Database:
    """Data-access layer wrapping a single SQLite connection."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Transaction helpers ───────────────────────────────────────────────

    def begin(self):
        self.conn.execute("BEGIN EXCLUSIVE TRANSACTION")

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.execute("ROLLBACK")

    # ── User ──────────────────────────────────────────────────────────────

    def get_user_by_credentials(self, username: str, password_hash: str):
        return self.conn.execute(
            "SELECT * FROM user WHERE username = ? AND password = ?",
            (username, password_hash),
        ).fetchone()

    def get_user_by_username(self, username: str):
        return self.conn.execute(
            "SELECT user_id FROM user WHERE username = ?", (username,)
        ).fetchone()

    def create_user(
        self, username: str, password_hash: str, email: str, role: str = "reader"
    ):
        self.conn.execute(
            "INSERT INTO user (username, password, email, role) VALUES (?,?,?,?)",
            (username, password_hash, email, role),
        )
        self.conn.commit()

    def get_all_users(self):
        return self.conn.execute(
            "SELECT * FROM user ORDER BY created_at DESC"
        ).fetchall()

    def delete_user(self, user_id: int):
        self.conn.execute(
            "DELETE FROM user WHERE user_id = ? AND role != 'admin'", (user_id,)
        )
        self.conn.commit()

    def count_users(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]

    # ── Category ──────────────────────────────────────────────────────────

    def get_all_categories(self):
        return self.conn.execute(
            "SELECT * FROM category ORDER BY category_id"
        ).fetchall()

    def create_category(self, name: str, description: str):
        self.conn.execute(
            "INSERT INTO category (name, description) VALUES (?, ?)",
            (name, description),
        )
        self.conn.commit()

    def update_category(self, category_id: int, name: str, description: str):
        self.conn.execute(
            "UPDATE category SET name=?, description=? WHERE category_id=?",
            (name, description, category_id),
        )
        self.conn.commit()

    def delete_category(self, category_id: int):
        self.conn.execute(
            "DELETE FROM category WHERE category_id = ?", (category_id,)
        )
        self.conn.commit()

    def count_categories(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM category").fetchone()[0]

    # ── Book ──────────────────────────────────────────────────────────────

    def get_book(self, book_id: int):
        return self.conn.execute(
            """
            SELECT b.*, c.name AS category_name,
                   COALESCE(vr.avg_rating, 0) AS avg_rating,
                   COALESCE(vr.review_count, 0) AS review_count
            FROM book b
            LEFT JOIN category c ON b.category_id = c.category_id
            LEFT JOIN view_book_rating vr ON b.book_id = vr.book_id
            WHERE b.book_id = ?
            """,
            (book_id,),
        ).fetchone()

    def get_books(self, category_id: str = "", keyword: str = ""):
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
            query += " AND b.category_id = ?"
            params.append(category_id)
        if keyword:
            query += " AND (b.title LIKE ? OR b.author LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        query += " ORDER BY b.book_id DESC"

        return self.conn.execute(query, params).fetchall()

    def get_popular_books(self, limit: int = 5):
        return self.conn.execute(
            """
            SELECT b.book_id, b.title, b.author,
                   COUNT(br.record_id) AS borrow_count
            FROM book b
            LEFT JOIN borrow_record br ON b.book_id = br.book_id
            GROUP BY b.book_id, b.title, b.author
            ORDER BY borrow_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def get_top_rated_books(self, limit: int = 6):
        return self.conn.execute(
            """
            SELECT * FROM view_book_rating
            ORDER BY avg_rating DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def create_book(
        self,
        title: str,
        author: str,
        isbn: str,
        published_date: str,
        total_copies: int,
        description: str,
        category_id: int | None,
    ):
        self.conn.execute(
            """
            INSERT INTO book (title, author, isbn, published_date, total_copies,
                              available_copies, description, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                author,
                isbn,
                published_date,
                total_copies,
                total_copies,  # available_copies starts equal to total_copies
                description,
                category_id,
            ),
        )
        self.conn.commit()

    def update_book(
        self,
        book_id: int,
        title: str,
        author: str,
        isbn: str,
        published_date: str,
        total_copies: int,
        description: str,
        category_id: int | None,
    ):
        self.conn.execute(
            """
            UPDATE book SET title=?, author=?, isbn=?, published_date=?,
            total_copies=?, description=?, category_id=?
            WHERE book_id=?
            """,
            (title, author, isbn, published_date, total_copies, description,
             category_id, book_id),
        )
        self.conn.commit()

    def delete_book(self, book_id: int):
        self.conn.execute("DELETE FROM book WHERE book_id = ?", (book_id,))
        self.conn.commit()

    def count_books(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]

    # ── Borrow ────────────────────────────────────────────────────────────

    def get_active_borrow(self, user_id: int, book_id: int):
        return self.conn.execute(
            """
            SELECT record_id FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND status = '借出'
            """,
            (user_id, book_id),
        ).fetchone()

    def get_borrow_record(self, record_id: int):
        return self.conn.execute(
            "SELECT * FROM borrow_record WHERE record_id = ?", (record_id,)
        ).fetchone()

    def get_user_borrows(self, user_id: int):
        return self.conn.execute(
            """
            SELECT br.*, b.title, b.author,
                   CASE WHEN br.return_date IS NULL AND br.due_date < DATE('now')
                        THEN '逾期' ELSE br.status END AS current_status
            FROM borrow_record br
            JOIN book b ON br.book_id = b.book_id
            WHERE br.user_id = ?
            ORDER BY br.borrow_date DESC
            """,
            (user_id,),
        ).fetchall()

    def get_all_borrows(self):
        return self.conn.execute(
            """
            SELECT br.*, u.username, b.title AS book_title,
                   CASE WHEN br.status = '借出' AND br.due_date < DATE('now')
                        THEN 1 ELSE 0 END AS is_overdue
            FROM borrow_record br
            JOIN user u ON br.user_id = u.user_id
            JOIN book b ON br.book_id = b.book_id
            ORDER BY br.borrow_date DESC
            """
        ).fetchall()

    def count_active_borrows(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM borrow_record WHERE status = '借出'"
        ).fetchone()[0]

    def get_overdue_borrows(self):
        return self.conn.execute(
            """
            SELECT u.username, u.email, b.title, br.borrow_date, br.due_date,
                   CAST(julianday('now') - julianday(br.due_date) AS INTEGER)
                       AS overdue_days
            FROM borrow_record br
            JOIN user u ON br.user_id = u.user_id
            JOIN book b ON br.book_id = b.book_id
            WHERE br.status = '借出' AND br.due_date < DATE('now')
            ORDER BY overdue_days DESC
            """
        ).fetchall()

    def user_has_returned_book(self, user_id: int, book_id: int):
        return self.conn.execute(
            """
            SELECT record_id FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND status = '已还'
            """,
            (user_id, book_id),
        ).fetchone()

    # ── Borrow / Return transactions ──────────────────────────────────────

    def borrow_book(self, user_id: int, book_id: int):
        """Execute full borrow transaction. Returns (ok, message, due_date_str|None)."""
        existing = self.get_active_borrow(user_id, book_id)
        if existing:
            return False, "您已借阅此书，不可重复借阅", None

        due_date = date.today() + timedelta(days=30)

        try:
            self.begin()

            book = self.conn.execute(
                "SELECT available_copies FROM book WHERE book_id = ?",
                (book_id,),
            ).fetchone()

            if not book:
                self.rollback()
                return False, "图书不存在", None

            avail = book["available_copies"]
            if avail > 0:
                self.conn.execute(
                    """
                    INSERT INTO borrow_record (user_id, book_id, borrow_date,
                                               due_date, status)
                    VALUES (?, ?, ?, ?, '借出')
                    """,
                    (user_id, book_id, date.today().isoformat(),
                     due_date.isoformat()),
                )
                self.conn.execute(
                    "UPDATE book SET available_copies = available_copies - 1 "
                    "WHERE book_id = ?",
                    (book_id,),
                )
                self.commit()
                return True, "借阅成功", due_date.isoformat()
            else:
                self.rollback()
                return False, "图书无可用副本，您可以预约此书", None
        except Exception as e:
            self.rollback()
            return False, str(e), None

    def return_book(self, record_id: int, user_id: int):
        """Execute full return transaction + reservation notification.
        Returns (ok, message)."""
        record = self.get_borrow_record(record_id)
        if not record or record["user_id"] != user_id:
            return False, "借阅记录不存在"
        if record["status"] == "已还":
            return False, "此书已归还"

        try:
            self.begin()

            self.conn.execute(
                """
                UPDATE borrow_record
                SET return_date = ?, status = '已还'
                WHERE record_id = ?
                """,
                (date.today().isoformat(), record_id),
            )

            self.conn.execute(
                "UPDATE book SET available_copies = available_copies + 1 "
                "WHERE book_id = ?",
                (record["book_id"],),
            )

            self.commit()

            # Check for pending reservation
            reservation = self.get_next_pending_reservation(record["book_id"])

            msg = "归还成功"
            if reservation:
                self.mark_reservation_available(reservation["reservation_id"])
                self.conn.commit()
                msg += "，已有预约用户可借阅此书"

            return True, msg
        except Exception as e:
            self.rollback()
            return False, str(e)

    def force_return(self, record_id: int):
        """Admin force-return a borrowed book."""
        record = self.get_borrow_record(record_id)
        if record and record["status"] == "借出":
            self.conn.execute(
                """
                UPDATE borrow_record
                SET return_date = ?, status = '已还'
                WHERE record_id = ?
                """,
                (date.today().isoformat(), record_id),
            )
            self.conn.execute(
                "UPDATE book SET available_copies = available_copies + 1 "
                "WHERE book_id = ?",
                (record["book_id"],),
            )
            self.conn.commit()

    # ── Reservation ───────────────────────────────────────────────────────

    def get_pending_reservation(self, user_id: int, book_id: int):
        return self.conn.execute(
            """
            SELECT reservation_id FROM reservation
            WHERE user_id = ? AND book_id = ? AND status = '待处理'
            """,
            (user_id, book_id),
        ).fetchone()

    def get_user_reservations(self, user_id: int):
        return self.conn.execute(
            """
            SELECT r.*, b.title, b.author
            FROM reservation r
            JOIN book b ON r.book_id = b.book_id
            WHERE r.user_id = ?
            ORDER BY r.reserve_date DESC
            """,
            (user_id,),
        ).fetchall()

    def get_all_reservations(self):
        return self.conn.execute(
            """
            SELECT r.*, u.username, b.title AS book_title
            FROM reservation r
            JOIN user u ON r.user_id = u.user_id
            JOIN book b ON r.book_id = b.book_id
            ORDER BY r.reserve_date DESC
            """
        ).fetchall()

    def count_pending_reservations(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM reservation WHERE status = '待处理'"
        ).fetchone()[0]

    def create_reservation(self, user_id: int, book_id: int):
        self.conn.execute(
            """
            INSERT INTO reservation (user_id, book_id, reserve_date, status)
            VALUES (?, ?, datetime('now', 'localtime'), '待处理')
            """,
            (user_id, book_id),
        )
        self.conn.commit()

    def cancel_reservation(self, reservation_id: int, user_id: int):
        self.conn.execute(
            """
            UPDATE reservation SET status = '已取消'
            WHERE reservation_id = ? AND user_id = ?
            """,
            (reservation_id, user_id),
        )
        self.conn.commit()

    def get_next_pending_reservation(self, book_id: int):
        return self.conn.execute(
            """
            SELECT * FROM reservation
            WHERE book_id = ? AND status = '待处理'
            ORDER BY reserve_date ASC
            LIMIT 1
            """,
            (book_id,),
        ).fetchone()

    def mark_reservation_available(self, reservation_id: int):
        self.conn.execute(
            "UPDATE reservation SET status = '可借' WHERE reservation_id = ?",
            (reservation_id,),
        )

    # ── Review ────────────────────────────────────────────────────────────

    def get_book_reviews(self, book_id: int):
        return self.conn.execute(
            """
            SELECT r.*, u.username
            FROM review r
            JOIN user u ON r.user_id = u.user_id
            WHERE r.book_id = ?
            ORDER BY r.created_at DESC
            """,
            (book_id,),
        ).fetchall()

    def user_has_reviewed(self, user_id: int, book_id: int):
        return self.conn.execute(
            "SELECT review_id FROM review WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()

    def create_review(
        self, user_id: int, book_id: int, rating: int, comment: str
    ) -> bool:
        try:
            self.conn.execute(
                """
                INSERT INTO review (user_id, book_id, rating, comment)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, book_id, rating, comment),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


# ── Factory ────────────────────────────────────────────────────────────────

def create_connection(db_path: str) -> sqlite3.Connection:
    """Create and configure a new SQLite connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
