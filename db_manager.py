import os
import psycopg2
from dotenv import load_dotenv # Chỉ dùng cho môi trường phát triển cục bộ

# Tải biến môi trường từ file .env (nếu có). Chỉ chạy khi phát triển cục bộ.
# Trên Render, các biến môi trường sẽ được tự động inject.
load_dotenv() 

def get_db_connection():
    """
    Thiết lập kết nối tới cơ sở dữ liệu PostgreSQL.
    Sử dụng DATABASE_URL từ biến môi trường.
    """
    # Lấy DATABASE_URL từ biến môi trường
    # Trên Render, biến này sẽ được cung cấp tự động.
    # Khi chạy cục bộ, bạn cần đặt nó trong file .env
    DATABASE_URL = os.environ.get('DATABASE_URL') 
    
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Please set it in .env or Render.")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise # Ném lỗi để biết vấn đề kết nối

def create_keys_table():
    """
    Tạo bảng 'keys' trong cơ sở dữ liệu nếu nó chưa tồn tại.
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id SERIAL PRIMARY KEY,
                key_value TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("Table 'keys' checked/created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback() # Hoàn tác nếu có lỗi
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def add_key_to_db(key_value):
    """
    Thêm một key mới vào cơ sở dữ liệu.
    Trả về True nếu thêm thành công, False nếu key đã tồn tại hoặc có lỗi.
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO keys (key_value) VALUES (%s)", (key_value,))
        conn.commit()
        print(f"Key '{key_value}' added successfully.")
        return True
    except psycopg2.errors.UniqueViolation:
        # Xử lý lỗi nếu key đã tồn tại (do UNIQUE NOT NULL constraint)
        conn.rollback() # Hoàn tác giao dịch
        print(f"Key '{key_value}' already exists.")
        return False
    except Exception as e:
        print(f"Error adding key '{key_value}': {e}")
        conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_all_keys_from_db():
    """
    Lấy tất cả các key từ cơ sở dữ liệu.
    """
    conn = None
    cur = None
    keys = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT key_value FROM keys")
        keys = [row[0] for row in cur.fetchall()]
        print("Fetched all keys.")
    except Exception as e:
        print(f"Error fetching keys: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return keys

def delete_key_from_db(key_value):
    """
    Xóa một key khỏi cơ sở dữ liệu.
    Trả về True nếu xóa thành công, False nếu không tìm thấy key hoặc có lỗi.
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM keys WHERE key_value = %s", (key_value,))
        conn.commit()
        if cur.rowcount > 0:
            print(f"Key '{key_value}' deleted successfully.")
            return True
        else:
            print(f"Key '{key_value}' not found.")
            return False
    except Exception as e:
        print(f"Error deleting key '{key_value}': {e}")
        conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
