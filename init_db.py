"""Database initialization script using SQL Server (schema based on a.sql)."""

import hashlib

import pyodbc

from config import DB_SERVER, DB_NAME


def get_conn_str(db: str = 'master') -> str:
    return (
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={DB_SERVER};'
        f'DATABASE={db};'
        f'Trusted_Connection=yes;'
    )


def init_db():
    # 1. Create database if not exists
    conn = pyodbc.connect(get_conn_str('master'), autocommit=True)
    cursor = conn.cursor()
    cursor.execute(f"""
        IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{DB_NAME}')
            CREATE DATABASE [{DB_NAME}]
    """)
    conn.close()

    # 2. Connect to bookstore and create schema
    conn = pyodbc.connect(get_conn_str(DB_NAME), autocommit=True)
    cursor = conn.cursor()

    # ── Drop existing objects in correct order ────────────────────────
    cursor.execute("""
        DROP VIEW IF EXISTS view_borrow_details;
        DROP VIEW IF EXISTS view_book_rating;
        DROP TABLE IF EXISTS borrow_record;
        DROP TABLE IF EXISTS reservation;
        DROP TABLE IF EXISTS review;
        DROP TABLE IF EXISTS book;
        DROP TABLE IF EXISTS category;
        DROP TABLE IF EXISTS [user];
    """)

    # ── Tables (based on a.sql) ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE [user] (
            user_id    INTEGER IDENTITY(1,1) NOT NULL,
            username   VARCHAR(50)  NOT NULL UNIQUE,
            password   VARCHAR(255) NOT NULL,
            email      VARCHAR(100),
            role       VARCHAR(10)  DEFAULT 'reader'
                       CHECK(role IN ('reader', 'admin')),
            created_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT PK_USER PRIMARY KEY (user_id)
        );

        CREATE TABLE category (
            category_id INTEGER IDENTITY(1,1) NOT NULL,
            name        VARCHAR(50)  NOT NULL,
            description VARCHAR(MAX),
            CONSTRAINT PK_CATEGORY PRIMARY KEY (category_id)
        );

        CREATE TABLE book (
            book_id          INTEGER IDENTITY(1,1) NOT NULL,
            category_id      INTEGER,
            title            VARCHAR(200) NOT NULL,
            author           VARCHAR(100),
            isbn             VARCHAR(20)  UNIQUE,
            published_date   DATE,
            total_copies     INTEGER      DEFAULT 1,
            available_copies INTEGER      DEFAULT 1,
            description      VARCHAR(MAX),
            CONSTRAINT PK_BOOK PRIMARY KEY (book_id),
            CONSTRAINT FK_BOOK_BELONG_CATEGORY FOREIGN KEY (category_id)
                REFERENCES category(category_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION
        );

        CREATE TABLE borrow_record (
            record_id   INTEGER IDENTITY(1,1) NOT NULL,
            user_id     INTEGER,
            book_id     INTEGER,
            borrow_date DATE        NOT NULL,
            due_date    DATE        NOT NULL,
            return_date DATE,
            status      VARCHAR(10) DEFAULT '借出'
                        CHECK(status IN ('借出', '已还', '逾期')),
            CONSTRAINT PK_BORROW_RECORD PRIMARY KEY (record_id),
            CONSTRAINT FK_BORROW_R_BORROW_USER FOREIGN KEY (user_id)
                REFERENCES [user](user_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION,
            CONSTRAINT FK_BORROW_R_BORROWED_BOOK FOREIGN KEY (book_id)
                REFERENCES book(book_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION
        );

        CREATE TABLE review (
            review_id  INTEGER IDENTITY(1,1) NOT NULL,
            book_id    INTEGER,
            user_id    INTEGER,
            rating     INTEGER CHECK(rating >= 1 AND rating <= 5),
            [comment]  VARCHAR(MAX),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT PK_REVIEW PRIMARY KEY (review_id),
            CONSTRAINT UQ_REVIEW_USER_BOOK UNIQUE (user_id, book_id),
            CONSTRAINT FK_REVIEW_COMMENT_USER FOREIGN KEY (user_id)
                REFERENCES [user](user_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION,
            CONSTRAINT FK_REVIEW_COMMETED_BOOK FOREIGN KEY (book_id)
                REFERENCES book(book_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION
        );

        CREATE TABLE reservation (
            reservation_id INTEGER IDENTITY(1,1) NOT NULL,
            book_id        INTEGER,
            user_id        INTEGER,
            reserve_date   DATETIME    DEFAULT CURRENT_TIMESTAMP,
            status         VARCHAR(10) DEFAULT '待处理'
                           CHECK(status IN ('待处理', '可借', '已取消')),
            CONSTRAINT PK_RESERVATION PRIMARY KEY (reservation_id),
            CONSTRAINT FK_RESERVAT_RESERVE_USER FOREIGN KEY (user_id)
                REFERENCES [user](user_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION,
            CONSTRAINT FK_RESERVAT_RESERVED_BOOK FOREIGN KEY (book_id)
                REFERENCES book(book_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION
        );
    """)

    # ── Indexes ──────────────────────────────────────────────────────
    cursor.execute("""
        CREATE INDEX borrow_FK    ON borrow_record (user_id);
        CREATE INDEX borrowed_FK  ON borrow_record (book_id);
        CREATE INDEX reserve_FK   ON reservation (user_id);
        CREATE INDEX reserved_FK  ON reservation (book_id);
        CREATE INDEX comment_FK   ON review (user_id);
        CREATE INDEX commeted_FK  ON review (book_id);
        CREATE INDEX idx_br_book_status ON borrow_record (book_id, status);
        CREATE INDEX idx_book_title      ON book (title);
        CREATE INDEX idx_book_author     ON book (author);
        CREATE INDEX idx_review_book     ON review (book_id);
        CREATE INDEX idx_res_book_status ON reservation (book_id, status);
    """)

    # ── Views ────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE VIEW view_borrow_details AS
        SELECT br.record_id, u.username, b.title, b.author,
               br.borrow_date, br.due_date, br.return_date, br.status
        FROM borrow_record br
        JOIN [user] u ON br.user_id = u.user_id
        JOIN book b ON br.book_id = b.book_id;

        CREATE VIEW view_book_rating AS
        SELECT b.book_id, b.title, b.author,
               ROUND(CAST(AVG(CAST(r.rating AS FLOAT)) AS FLOAT), 1) AS avg_rating,
               COUNT(r.review_id) AS review_count
        FROM book b
        LEFT JOIN review r ON b.book_id = r.book_id
        GROUP BY b.book_id, b.title, b.author;
    """)

    # ── Seed data ────────────────────────────────────────────────────
    pw = hashlib.sha256('123456'.encode()).hexdigest()

    # Users
    cursor.execute(f"""
        SET IDENTITY_INSERT [user] ON;
        INSERT INTO [user] (user_id, username, password, email, role) VALUES
        (1, 'admin',   '{pw}', 'admin@lib.com',      'admin'),
        (2, 'reader1', '{pw}', 'reader1@email.com',  'reader'),
        (3, 'reader2', '{pw}', 'reader2@email.com',  'reader'),
        (4, 'reader3', '{pw}', 'reader3@email.com',  'reader');
        SET IDENTITY_INSERT [user] OFF;
    """)

    # Categories
    cursor.execute("""
        SET IDENTITY_INSERT category ON;
        INSERT INTO category (category_id, name, description) VALUES
        (1, N'计算机科学', N'计算机编程、算法、人工智能等'),
        (2, N'文学小说',   N'中外文学名著、当代小说'),
        (3, N'历史哲学',   N'历史研究、哲学思想类书籍'),
        (4, N'自然科学',   N'数学、物理、化学、生物等'),
        (5, N'经济管理',   N'经济学、管理学、市场营销'),
        (6, N'外语学习',   N'英语、日语等外语教材与读物');
        SET IDENTITY_INSERT category OFF;
    """)

    # Books
    cursor.execute("""
        SET IDENTITY_INSERT book ON;
        INSERT INTO book (book_id, category_id, title, author, isbn, published_date,
                          total_copies, available_copies, description) VALUES
        (1,  1, N'数据库系统概论',       N'王珊',             '9787040406641', '2014-09-01', 5, 5, N'全面介绍数据库系统的基本概念、原理和方法'),
        (2,  1, N'算法导论',             N'Thomas H. Cormen', '9787111407010', '2013-01-01', 3, 3, N'计算机算法领域的经典教材'),
        (3,  1, N'Python编程从入门到实践', N'Eric Matthes',    '9787115428028', '2016-07-01', 4, 4, N'零基础学Python的入门书'),
        (4,  1, N'深入理解计算机系统',   N'Randal E. Bryant', '9787111544937', '2016-11-01', 3, 3, N'从程序员视角理解计算机系统'),
        (5,  2, N'百年孤独',             N'马尔克斯',         '9787544253994', '2011-06-01', 4, 4, N'拉丁美洲魔幻现实主义代表作'),
        (6,  2, N'活着',                 N'余华',             '9787530215319', '2012-08-01', 5, 5, N'讲述人承受苦难的坚韧'),
        (7,  2, N'三体',                 N'刘慈欣',           '9787536692930', '2008-01-01', 6, 6, N'中国科幻文学的里程碑'),
        (8,  3, N'人类简史',             N'尤瓦尔·赫拉利',    '9787508647357', '2014-11-01', 4, 4, N'从认知革命到人工智能的人类历史'),
        (9,  3, N'苏菲的世界',           N'乔斯坦·贾德',      '9787506341271', '2007-10-01', 3, 3, N'以小说形式讲述西方哲学史'),
        (10, 4, N'时间简史',             N'史蒂芬·霍金',      '9787535732309', '2010-05-01', 3, 3, N'关于宇宙本性的最前沿知识'),
        (11, 5, N'经济学原理',           N'曼昆',             '9787301150894', '2009-04-01', 4, 4, N'最流行的经济学入门教材'),
        (12, 5, N'乔布斯传',             N'沃尔特·艾萨克森',  '9787508630069', '2011-10-01', 3, 3, N'史蒂夫·乔布斯的唯一授权传记');
        SET IDENTITY_INSERT book OFF;
    """)

    # Borrow records
    cursor.execute("""
        SET IDENTITY_INSERT borrow_record ON;
        INSERT INTO borrow_record (record_id, user_id, book_id, borrow_date, due_date, return_date, status) VALUES
        (1, 2, 1, '2024-11-30', '2024-12-30', NULL,          N'借出'),
        (2, 2, 2, '2024-12-05', '2025-01-04', NULL,          N'借出'),
        (3, 3, 3, '2024-11-05', '2024-12-05', '2024-12-07', N'已还'),
        (4, 3, 5, '2024-12-10', '2025-01-09', NULL,          N'借出');
        SET IDENTITY_INSERT borrow_record OFF;
    """)

    # Update available_copies for currently borrowed books
    cursor.execute("""
        UPDATE book SET available_copies = available_copies - 1 WHERE book_id = 1;
        UPDATE book SET available_copies = available_copies - 1 WHERE book_id = 2;
        UPDATE book SET available_copies = available_copies - 1 WHERE book_id = 5;
    """)

    # Reviews
    cursor.execute("""
        SET IDENTITY_INSERT review ON;
        INSERT INTO review (review_id, user_id, book_id, rating, [comment], created_at) VALUES
        (1, 3, 3, 5, N'非常好的入门书，很适合新手学习Python', '2024-11-20'),
        (2, 2, 1, 4, N'数据库课程经典教材，内容详实',         '2024-10-15'),
        (3, 3, 5, 5, N'读完后震撼人心，马尔克斯的文笔太优美了', '2024-11-25');
        SET IDENTITY_INSERT review OFF;
    """)

    # Reservations
    cursor.execute("""
        SET IDENTITY_INSERT reservation ON;
        INSERT INTO reservation (reservation_id, user_id, book_id, reserve_date, status) VALUES
        (1, 3, 2, '2024-12-01', N'待处理');
        SET IDENTITY_INSERT reservation OFF;
    """)

    conn.close()
    print(f'Database initialized successfully at: {DB_SERVER}/{DB_NAME}')


if __name__ == '__main__':
    init_db()
