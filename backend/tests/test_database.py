import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.core import User
from app.models.transaction import Transaction

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db():
    # Create the tables in the test database
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    # Teardown
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_create_user(db):
    user = User(email="test@example.com", hashed_password="hashed_password", role="ADMIN")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.role == "ADMIN"
    assert user.is_active is True

def test_create_transaction(db):
    tx = Transaction(
        id="TXN123",
        user_id="U1",
        merchant_id="M1",
        amount=100.50,
        currency="USD",
        payment_method="CREDIT_CARD",
        status="PENDING"
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    
    assert tx.id == "TXN123"
    assert tx.amount == 100.50
    assert tx.status == "PENDING"
