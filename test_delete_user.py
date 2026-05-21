from db import create_connection, Database
import traceback

def main():
    conn = None
    try:
        conn = create_connection()
        db = Database(conn)
        try:
            db.delete_user(2)
            print('删除用户成功')
        except Exception as e:
            print('出现错误:', e)
    except Exception as e:
        print('无法连接数据库或发生异常:', e)
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
