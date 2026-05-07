"""Database initialization script for Online Book Management System."""

import sqlite3
import os

DB_NAME = 'bookstore.db'


def get_db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)


def init_db():
    db_path = get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        PRAGMA foreign_keys = ON;

        -- ============================================================
        -- TABLES (6 tables, all satisfy 3NF)
        -- ============================================================

        CREATE TABLE user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(100),
            role VARCHAR(10) DEFAULT 'reader' CHECK(role IN ('reader', 'admin')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE category (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) NOT NULL,
            description TEXT
        );

        CREATE TABLE book (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            author VARCHAR(100),
            isbn VARCHAR(20) UNIQUE,
            published_date DATE,
            total_copies INT DEFAULT 1,
            available_copies INT DEFAULT 1,
            description TEXT,
            category_id INT,
            FOREIGN KEY (category_id) REFERENCES category(category_id)
        );

        CREATE TABLE borrow_record (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            borrow_date DATE NOT NULL,
            due_date DATE NOT NULL,
            return_date DATE,
            status VARCHAR(10) DEFAULT '借出' CHECK(status IN ('借出', '已还', '逾期')),
            FOREIGN KEY (user_id) REFERENCES user(user_id),
            FOREIGN KEY (book_id) REFERENCES book(book_id)
        );

        CREATE TABLE review (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            rating INT CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user(user_id),
            FOREIGN KEY (book_id) REFERENCES book(book_id),
            UNIQUE(user_id, book_id)
        );

        CREATE TABLE reservation (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            reserve_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(10) DEFAULT '待处理' CHECK(status IN ('待处理', '可借', '已取消')),
            FOREIGN KEY (user_id) REFERENCES user(user_id),
            FOREIGN KEY (book_id) REFERENCES book(book_id)
        );

        -- ============================================================
        -- VIEWS
        -- ============================================================

        -- View 1: Borrow details with user and book info
        CREATE VIEW view_borrow_details AS
        SELECT br.record_id, u.username, b.title, b.author,
               br.borrow_date, br.due_date, br.return_date, br.status
        FROM borrow_record br
        JOIN user u ON br.user_id = u.user_id
        JOIN book b ON br.book_id = b.book_id;

        -- View 2: Book average rating and review count
        CREATE VIEW view_book_rating AS
        SELECT b.book_id, b.title, b.author,
               ROUND(AVG(r.rating), 1) AS avg_rating,
               COUNT(r.review_id) AS review_count
        FROM book b
        LEFT JOIN review r ON b.book_id = r.book_id
        GROUP BY b.book_id, b.title, b.author;

        -- ============================================================
        -- INDEXES
        -- ============================================================

        -- Index on borrow_record(user_id) for fast user borrow history lookup
        CREATE INDEX idx_br_user ON borrow_record(user_id);

        -- Composite index on borrow_record(book_id, status) for checking book availability
        CREATE INDEX idx_br_book_status ON borrow_record(book_id, status);

        -- Indexes on book(title) and book(author) for fuzzy search
        CREATE INDEX idx_book_title ON book(title);
        CREATE INDEX idx_book_author ON book(author);

        -- Index on review(book_id) for aggregation queries
        CREATE INDEX idx_review_book ON review(book_id);

        -- Index on reservation(book_id, status) for checking reservation queue
        CREATE INDEX idx_res_book_status ON reservation(book_id, status);
    """)

    # ============================================================
    # SEED DATA
    # ============================================================

    # Users (password is hashed in app, here plain for seed: '123456')
    import hashlib
    pw = hashlib.sha256('123456'.encode()).hexdigest()

    users = [
        ('admin', pw, 'admin@lib.com', 'admin'),
        ('reader1', pw, 'reader1@email.com', 'reader'),
        ('reader2', pw, 'reader2@email.com', 'reader'),
        ('reader3', pw, 'reader3@email.com', 'reader'),
    ]
    cursor.executemany(
        'INSERT INTO user (username, password, email, role) VALUES (?,?,?,?)', users)

    # Categories
    categories = [
        ('计算机科学', '计算机编程、算法、人工智能等'),
        ('文学小说', '中外文学名著、当代小说'),
        ('历史哲学', '历史研究、哲学思想类书籍'),
        ('自然科学', '数学、物理、化学、生物等'),
        ('经济管理', '经济学、管理学、市场营销'),
        ('外语学习', '英语、日语等外语教材与读物'),
    ]
    cursor.executemany(
        'INSERT INTO category (name, description) VALUES (?,?)', categories)

    # Books
    books = [
        ('数据库系统概论', '王珊', '9787040406641', '2014-09-01', 5, 5,
         '全面介绍数据库系统的基本概念、原理和方法', 1),
        ('算法导论', 'Thomas H. Cormen', '9787111407010', '2013-01-01', 3, 3,
         '计算机算法领域的经典教材', 1),
        ('Python编程从入门到实践', 'Eric Matthes', '9787115428028', '2016-07-01', 4, 4,
         '零基础学Python的入门书', 1),
        ('深入理解计算机系统', 'Randal E. Bryant', '9787111544937', '2016-11-01', 3, 3,
         '从程序员视角理解计算机系统', 1),
        ('百年孤独', '马尔克斯', '9787544253994', '2011-06-01', 4, 4,
         '拉丁美洲魔幻现实主义代表作', 2),
        ('活着', '余华', '9787530215319', '2012-08-01', 5, 5,
         '讲述人承受苦难的坚韧', 2),
        ('三体', '刘慈欣', '9787536692930', '2008-01-01', 6, 6,
         '中国科幻文学的里程碑', 2),
        ('人类简史', '尤瓦尔·赫拉利', '9787508647357', '2014-11-01', 4, 4,
         '从认知革命到人工智能的人类历史', 3),
        ('苏菲的世界', '乔斯坦·贾德', '9787506341271', '2007-10-01', 3, 3,
         '以小说形式讲述西方哲学史', 3),
        ('时间简史', '史蒂芬·霍金', '9787535732309', '2010-05-01', 3, 3,
         '关于宇宙本性的最前沿知识', 4),
        ('经济学原理', '曼昆', '9787301150894', '2009-04-01', 4, 4,
         '最流行的经济学入门教材', 5),
        ('乔布斯传', '沃尔特·艾萨克森', '9787508630069', '2011-10-01', 3, 3,
         '史蒂夫·乔布斯的唯一授权传记', 5),
    ]
    cursor.executemany(
        '''INSERT INTO book (title, author, isbn, published_date, total_copies,
           available_copies, description, category_id)
           VALUES (?,?,?,?,?,?,?,?)''', books)

    # Some borrow records for demo
    from datetime import date, timedelta
    today = date.today()

    borrow_records = [
        (2, 1, today - timedelta(days=15), today + timedelta(days=15),
         None, '借出'),
        (2, 2, today - timedelta(days=10), today + timedelta(days=20),
         None, '借出'),
        (3, 3, today - timedelta(days=40), today - timedelta(days=10),
         today - timedelta(days=8), '已还'),
        (3, 5, today - timedelta(days=5), today + timedelta(days=25),
         None, '借出'),
    ]
    # Update available_copies for borrowed books
    for rec in borrow_records:
        if rec[5] == '借出':
            cursor.execute(
                'UPDATE book SET available_copies = available_copies - 1 WHERE book_id = ?',
                (rec[1],))

    cursor.executemany(
        '''INSERT INTO borrow_record (user_id, book_id, borrow_date, due_date,
           return_date, status) VALUES (?,?,?,?,?,?)''', borrow_records)

    # Reviews
    reviews = [
        (3, 3, 5, '非常好的入门书，很适合新手学习Python', '2024-11-20'),
        (2, 1, 4, '数据库课程经典教材，内容详实', '2024-10-15'),
        (3, 5, 5, '读完后震撼人心，马尔克斯的文笔太优美了', '2024-11-25'),
    ]
    cursor.executemany(
        '''INSERT INTO review (user_id, book_id, rating, comment, created_at)
           VALUES (?,?,?,?,?)''', reviews)

    # Reservations
    reservations = [
        (3, 2, '2024-12-01', '待处理'),
    ]
    cursor.executemany(
        'INSERT INTO reservation (user_id, book_id, reserve_date, status) VALUES (?,?,?,?)',
        reservations)

    conn.commit()
    conn.close()
    print(f'Database initialized successfully at: {db_path}')


if __name__ == '__main__':
    init_db()
