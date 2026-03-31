from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    transactions = relationship("Transaction", back_populates="owner")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    transactions = relationship("Transaction", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True)
    amount = Column(Float)
    date = Column(DateTime)
    raw_category = Column(String, nullable=True)
    final_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    status = Column(String, default="pending") # e.g., pending, categorized, needs_review
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    __table_args__ = (UniqueConstraint('owner_id', 'description', 'amount', 'date', name='_owner_transaction_uc'),)

# Dimension Tables for Star Schema
class CustomerDimension(Base):
    __tablename__ = "customer_dimension"
    customer_sk = Column(Integer, primary_key=True, index=True) # Surrogate Key
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    email = Column(String)
    # Add other customer attributes as needed

class DateDimension(Base):
    __tablename__ = "date_dimension"
    date_sk = Column(Integer, primary_key=True, index=True) # Surrogate Key
    full_date = Column(DateTime, unique=True)
    day = Column(Integer)
    month = Column(Integer)
    year = Column(Integer)
    quarter = Column(Integer)
    day_of_week = Column(Integer)
    day_name = Column(String)
    month_name = Column(String)
    # Add other date attributes as needed

class CategoryDimension(Base):
    __tablename__ = "category_dimension"
    category_sk = Column(Integer, primary_key=True, index=True) # Surrogate Key
    category_id = Column(Integer, ForeignKey("categories.id"), unique=True)
    name = Column(String)
    # Add other category attributes as needed

# Fact Table
class TransactionFact(Base):
    __tablename__ = "transactions_fact"
    transaction_sk = Column(Integer, primary_key=True, index=True) # Surrogate Key
    transaction_id = Column(Integer, ForeignKey("transactions.id"), unique=True)
    customer_sk = Column(Integer, ForeignKey("customer_dimension.customer_sk"))
    date_sk = Column(Integer, ForeignKey("date_dimension.date_sk"))
    category_sk = Column(Integer, ForeignKey("category_dimension.category_sk"), nullable=True)
    amount = Column(Float)
    # Add other measures/facts as needed

