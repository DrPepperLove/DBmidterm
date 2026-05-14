"""Database abstraction layer for the Online Book Management System.

Encapsulates all SQL Server operations behind a clean API, organized by domain entity.
"""

from datetime import date, timedelta

import pyodbc

from config import DB_SERVER, DB_NAME


class _DictCursor:
    """Wrap a pyodbc cursor so fetchone/fetchall return dicts keyed by column name."""

    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [d[0] for d in cursor.description] if cursor.description else []

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(zip(self._columns, row))

    def fetchall(self):
        return [dict(zip(self._columns, r)) for r in self._cursor.fetchall()]


class Database:
    """Data-access layer wrapping a single pyodbc connection."""

    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn

    def _execute(self, sql: str, params=None):
        cursor = self.conn.cursor()
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return _DictCursor(cursor)

    # -- Transaction helpers -------------------------------------------

    def begin(self):
        self._execute("BEGIN TRANSACTION")

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    # -- User ---------------------------------------------------------

    def get_user_by_credentials(self, username: str, password_hash: str):
        return self._execute(
            "SELECT * FROM [user] WHERE username = ? AND password = ?",
            (username, password_hash),
        ).fetchone()

    def get_user_by_username(self, username: str):
        return self._execute(
            "SELECT user_id FROM [user] WHERE username = ?", (username,)
        ).fetchone()

    def create_user(
        self, username: str, password_hash: str, email: str, role: str = "reader"
    ):
        self._execute(
            "INSERT INTO [user] (username, password, email, role) VALUES (?,?,?,?)",
            (username, password_hash, email, role),
        )
        self.conn.commit()

    def get_all_users(self):
        return self._execute(
            "SELECT * FROM [user] ORDER BY created_at DESC"
        ).fetchall()

    def delete_user(self, user_id: int):
        self._execute(
            "DELETE FROM [user] WHERE user_id = ? AND role != 'admin'", (user_id,)
        )
        self.conn.commit()

    def count_users(self) -> int:
        return self._execute("SELECT COUNT(*) AS cnt FROM [user]").fetchone()["cnt"]

    # -- Category -----------------------------------------------------

    def get_all_categories(self):
        return self._execute(
            "SELECT * FROM category ORDER BY category_id"
        ).fetchall()

    def create_category(self, name: str, description: str):
        self._execute(
            "INSERT INTO category (name, description) VALUES (?, ?)",
            (name, description),
        )
        self.conn.commit()

    def update_category(self, category_id: int, name: str, description: str):
        self._execute(
            "UPDATE category SET name=?, description=? WHERE category_id=?",
            (name, description, category_id),
        )
        self.conn.commit()

    def delete_category(self, category_id: int):
        self._execute(
            "DELETE FROM category WHERE category_id = ?", (category_id,)
        )
        self.conn.commit()

    def count_categories(self) -> int:
        return self._execute("SELECT COUNT(*) AS cnt FROM category").fetchone()["cnt"]

    # -- Book ---------------------------------------------------------

    def get_book(self, book_id: int):
        return self._execute(
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

        return self._execute(query, params).fetchall()

    def get_popular_books(self, limit: int = 5):
        return self._execute(f"""
            SELECT TOP {limit} b.book_id, b.title, b.author,
                   COUNT(br.record_id) AS borrow_count
            FROM book b
            LEFT JOIN borrow_record br ON b.book_id = br.book_id
            GROUP BY b.book_id, b.title, b.author
            ORDER BY borrow_count DESC
        """).fetchall()

    def get_top_rated_books(self, limit: int = 6):
        return self._execute(f"""
            SELECT TOP {limit} * FROM view_book_rating
            ORDER BY avg_rating DESC
        """).fetchall()

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
        self._execute(
            """
            INSERT INTO book (title, author, isbn, published_date, total_copies,
                              available_copies, description, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title, author, isbn, published_date,
                total_copies, total_copies, description, category_id,
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
        self._execute(
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
        self._execute("DELETE FROM book WHERE book_id = ?", (book_id,))
        self.conn.commit()

    def count_books(self) -> int:
        return self._execute("SELECT COUNT(*) AS cnt FROM book").fetchone()["cnt"]

    # -- Borrow -------------------------------------------------------

    def get_active_borrow(self, user_id: int, book_id: int):
        return self._execute(
            """
            SELECT record_id FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND status = N'借出'
            """,
            (user_id, book_id),
        ).fetchone()

    def get_borrow_record(self, record_id: int):
        return self._execute(
            "SELECT * FROM borrow_record WHERE record_id = ?", (record_id,)
        ).fetchone()

    def get_user_borrows(self, user_id: int):
        return self._execute(
            """
            SELECT br.*, b.title, b.author,
                   CASE WHEN br.return_date IS NULL
                         AND br.due_date < CAST(GETDATE() AS DATE)
                        THEN N'逾期' ELSE br.status END AS current_status
            FROM borrow_record br
            JOIN book b ON br.book_id = b.book_id
            WHERE br.user_id = ?
            ORDER BY br.borrow_date DESC
            """,
            (user_id,),
        ).fetchall()

    def get_all_borrows(self):
        return self._execute(
            """
            SELECT br.*, u.username, b.title AS book_title,
                   CASE WHEN br.status = N'借出'
                         AND br.due_date < CAST(GETDATE() AS DATE)
                        THEN 1 ELSE 0 END AS is_overdue
            FROM borrow_record br
            JOIN [user] u ON br.user_id = u.user_id
            JOIN book b ON br.book_id = b.book_id
            ORDER BY br.borrow_date DESC
            """
        ).fetchall()

    def count_active_borrows(self) -> int:
        return self._execute(
            "SELECT COUNT(*) AS cnt FROM borrow_record WHERE status = N'借出'"
        ).fetchone()["cnt"]

    def get_overdue_borrows(self):
        return self._execute(
            """
            SELECT u.username, u.email, b.title, br.borrow_date, br.due_date,
                   DATEDIFF(DAY, br.due_date, GETDATE()) AS overdue_days
            FROM borrow_record br
            JOIN [user] u ON br.user_id = u.user_id
            JOIN book b ON br.book_id = b.book_id
            WHERE br.status = N'借出' AND br.due_date < CAST(GETDATE() AS DATE)
            ORDER BY overdue_days DESC
            """
        ).fetchall()

    def user_has_returned_book(self, user_id: int, book_id: int):
        return self._execute(
            """
            SELECT record_id FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND status = N'已还'
            """,
            (user_id, book_id),
        ).fetchone()

    # -- Borrow / Return transactions ---------------------------------

    def borrow_book(self, user_id: int, book_id: int):
        """Execute full borrow transaction. Returns (ok, message, due_date_str|None)."""
        existing = self.get_active_borrow(user_id, book_id)
        if existing:
            return False, "您已借阅此书，不可重复借阅", None

        due_date = date.today() + timedelta(days=30)

        try:
            self.begin()

            book = self._execute(
                "SELECT available_copies FROM book WHERE book_id = ?",
                (book_id,),
            ).fetchone()

            if not book:
                self.rollback()
                return False, "图书不存在", None

            avail = book["available_copies"]
            if avail > 0:
                self._execute(
                    """
                    INSERT INTO borrow_record (user_id, book_id, borrow_date,
                                               due_date, status)
                    VALUES (?, ?, ?, ?, N'借出')
                    """,
                    (user_id, book_id, date.today().isoformat(),
                     due_date.isoformat()),
                )
                self._execute(
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

            self._execute(
                """
                UPDATE borrow_record
                SET return_date = ?, status = N'已还'
                WHERE record_id = ?
                """,
                (date.today().isoformat(), record_id),
            )

            self._execute(
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
            self._execute(
                """
                UPDATE borrow_record
                SET return_date = ?, status = N'已还'
                WHERE record_id = ?
                """,
                (date.today().isoformat(), record_id),
            )
            self._execute(
                "UPDATE book SET available_copies = available_copies + 1 "
                "WHERE book_id = ?",
                (record["book_id"],),
            )
            self.conn.commit()

    # -- Reservation --------------------------------------------------

    def get_pending_reservation(self, user_id: int, book_id: int):
        return self._execute(
            """
            SELECT reservation_id FROM reservation
            WHERE user_id = ? AND book_id = ? AND status = N'待处理'
            """,
            (user_id, book_id),
        ).fetchone()

    def get_user_reservations(self, user_id: int):
        return self._execute(
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
        return self._execute(
            """
            SELECT r.*, u.username, b.title AS book_title
            FROM reservation r
            JOIN [user] u ON r.user_id = u.user_id
            JOIN book b ON r.book_id = b.book_id
            ORDER BY r.reserve_date DESC
            """
        ).fetchall()

    def count_pending_reservations(self) -> int:
        return self._execute(
            "SELECT COUNT(*) AS cnt FROM reservation WHERE status = N'待处理'"
        ).fetchone()["cnt"]

    def create_reservation(self, user_id: int, book_id: int):
        self._execute(
            """
            INSERT INTO reservation (user_id, book_id, reserve_date, status)
            VALUES (?, ?, GETDATE(), N'待处理')
            """,
            (user_id, book_id),
        )
        self.conn.commit()

    def cancel_reservation(self, reservation_id: int, user_id: int):
        self._execute(
            """
            UPDATE reservation SET status = N'已取消'
            WHERE reservation_id = ? AND user_id = ?
            """,
            (reservation_id, user_id),
        )
        self.conn.commit()

    def get_next_pending_reservation(self, book_id: int):
        return self._execute(
            """
            SELECT TOP 1 * FROM reservation
            WHERE book_id = ? AND status = N'待处理'
            ORDER BY reserve_date ASC
            """,
            (book_id,),
        ).fetchone()

    def mark_reservation_available(self, reservation_id: int):
        self._execute(
            "UPDATE reservation SET status = N'可借' WHERE reservation_id = ?",
            (reservation_id,),
        )

    # -- Review -------------------------------------------------------

    def get_book_reviews(self, book_id: int):
        return self._execute(
            """
            SELECT r.*, u.username
            FROM review r
            JOIN [user] u ON r.user_id = u.user_id
            WHERE r.book_id = ?
            ORDER BY r.created_at DESC
            """,
            (book_id,),
        ).fetchall()

    def user_has_reviewed(self, user_id: int, book_id: int):
        return self._execute(
            "SELECT review_id FROM review WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()

    def create_review(
        self, user_id: int, book_id: int, rating: int, comment: str
    ) -> bool:
        try:
            self._execute(
                """
                INSERT INTO review (user_id, book_id, rating, [comment])
                VALUES (?, ?, ?, ?)
                """,
                (user_id, book_id, rating, comment),
            )
            self.conn.commit()
            return True
        except pyodbc.IntegrityError:
            return False


# -- Factory ----------------------------------------------------------

def create_connection() -> pyodbc.Connection:
    """Create and configure a new pyodbc connection to SQL Server."""
    conn_str = (
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={DB_SERVER};'
        f'DATABASE={DB_NAME};'
        f'Trusted_Connection=yes;'
    )
    return pyodbc.connect(conn_str)
