import pytest
import concurrent.futures
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from app.core.config import settings

# Ensure we use Postgres for this test
TEST_DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/risk_manager")

engine = create_engine(TEST_DB_URL, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_postgres_connection():
    # Simple connection check
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

def test_transaction_rollback():
    # Test that a rollback correctly undoes changes
    session = SessionLocal()
    
    # create table
    session.execute(text("CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, val INT)"))
    session.commit()
    
    session.execute(text("INSERT INTO test_table (val) VALUES (10)"))
    session.commit()
    
    # Start a transaction and rollback
    try:
        session.execute(text("INSERT INTO test_table (val) VALUES (20)"))
        raise ValueError("Simulated failure")
        session.commit()
    except ValueError:
        session.rollback()
        
    # verify 20 is not there
    result = session.execute(text("SELECT val FROM test_table WHERE val=20")).fetchall()
    assert len(result) == 0
    session.close()

def test_concurrent_access():
    # clean up the table first
    session = SessionLocal()
    session.execute(text("CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, val INT)"))
    session.execute(text("DELETE FROM test_table WHERE val >= 100"))
    session.commit()
    session.close()

    def write_val(val):
        session = SessionLocal()
        try:
            session.execute(text("INSERT INTO test_table (val) VALUES (:v)"), {"v": val})
            session.commit()
        finally:
            session.close()
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_val, 100 + i) for i in range(10)]
        concurrent.futures.wait(futures)
        
    session = SessionLocal()
    results = session.execute(text("SELECT val FROM test_table WHERE val >= 100")).fetchall()
    assert len(results) == 10
    session.close()
