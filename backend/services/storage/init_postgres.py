"""
Initialize PostgreSQL Database Schema
Creates tables for users and quiz results
"""

import psycopg2
from psycopg2 import sql
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


def init_postgres_schema():
    """Initialize PostgreSQL database schema"""

    print("=" * 70)
    print("Initializing PostgreSQL Schema")
    print("=" * 70)
    print()

    # Connection parameters
    conn_params = {
        'host': config.POSTGRES_HOST,
        'port': config.POSTGRES_PORT,
        'database': config.POSTGRES_DB,
        'user': config.POSTGRES_USER,
        'password': config.POSTGRES_PASSWORD
    }

    print(f"Connecting to PostgreSQL:")
    print(f"  Host: {conn_params['host']}")
    print(f"  Database: {conn_params['database']}")
    print(f"  User: {conn_params['user']}")
    print()

    try:
        # Connect to database
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        print("✅ Connected to PostgreSQL")
        print()

        # Create users table
        print("Creating 'users' table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(255) PRIMARY KEY,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                metadata JSONB
            )
        """)
        print("✅ 'users' table created")

        # Create index on email
        print("Creating index on email...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
        """)
        print("✅ Email index created")
        print()

        # Create quiz_results table
        print("Creating 'quiz_results' table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                quiz_id VARCHAR(255) NOT NULL,
                score INTEGER,
                total_questions INTEGER,
                answers JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                metadata JSONB,
                CONSTRAINT fk_user FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
        """)
        print("✅ 'quiz_results' table created")

        # Create indexes for quiz_results
        print("Creating quiz_results indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_quiz_results_username
            ON quiz_results(username)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_quiz_results_quiz_id
            ON quiz_results(quiz_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_quiz_results_created_at
            ON quiz_results(created_at DESC)
        """)
        print("✅ Quiz results indexes created")
        print()

        # Commit changes
        conn.commit()

        # Verify tables
        print("Verifying tables...")
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        print("✅ Tables in database:")
        for table in tables:
            print(f"  • {table[0]}")
        print()

        # Close connection
        cur.close()
        conn.close()

        print("=" * 70)
        print("✅ PostgreSQL Schema Initialized Successfully!")
        print("=" * 70)
        print()
        print("Ready to use hybrid storage (PostgreSQL + DynamoDB)")

        return True

    except Exception as e:
        print(f"❌ Error initializing schema: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    init_postgres_schema()
