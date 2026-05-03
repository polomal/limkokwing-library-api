"""
Limkokwing Library Management API
A comprehensive RESTful API for managing library operations including books,
users, borrowing, and returning books with fine calculations.

Author: Library Management System
Version: 1.0.0
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from enum import Enum
import uuid
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App Configuration
app = FastAPI(
    title="Limkokwing Library API",
    description="A comprehensive library management system with book borrowing, returning, and fine management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory database
books: Dict[str, Dict[str, Any]] = {}
users: Dict[str, Dict[str, Any]] = {}
loans: Dict[str, Dict[str, Any]] = {}
fines: Dict[str, Dict[str, Any]] = {}

# Async lock for thread-safe operations
lock = asyncio.Lock()

# Constants
FINE_PER_DAY = 0.50
MAX_BORROW_DAYS = 90
MIN_BORROW_DAYS = 1


# Enums
class BorrowStatus(str, Enum):
    """Status of a book borrow"""
    BORROWED = "borrowed"
    RETURNED = "returned"
    OVERDUE = "overdue"


# Pydantic Models
class BookOut(BaseModel):
    """Book output model"""
    id: str
    title: str
    author: str
    category: str
    available: int
    total: int

    class Config:
        json_json_schema_extra = {
            "example": {
                "id": "b1",
                "title": "Learning Python",
                "author": "Guido van Rossum",
                "category": "Programming",
                "available": 3,
                "total": 5
            }
        }


class UserOut(BaseModel):
    """User output model"""
    id: str
    name: str
    email: str
    member_since: datetime
    active_loans: int

    class Config:
        json_json_schema_extra = {
            "example": {
                "id": "u123",
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "member_since": "2024-01-15T10:30:00Z",
                "active_loans": 2
            }
        }


class BorrowRequest(BaseModel):
    """Request model for borrowing a book"""
    user_id: str = Field(..., description="User ID")
    book_id: str = Field(..., description="Book ID")
    days: int = Field(default=14, ge=MIN_BORROW_DAYS, le=MAX_BORROW_DAYS, description="Number of days to borrow (1-90)")

    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('User ID cannot be empty')
        return v.strip()

    @validator('book_id')
    def validate_book_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Book ID cannot be empty')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "u123",
                "book_id": "b1",
                "days": 14
            }
        }


class ReturnRequest(BaseModel):
    """Request model for returning a book"""
    user_id: str = Field(..., description="User ID")
    book_id: str = Field(..., description="Book ID")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "u123",
                "book_id": "b1"
            }
        }


class LoanRecord(BaseModel):
    """Loan record model"""
    loan_id: str
    user_id: str
    book_id: str
    borrowed_at: datetime
    due_date: datetime
    returned_at: Optional[datetime] = None
    status: str
    fine: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "loan_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "u123",
                "book_id": "b1",
                "borrowed_at": "2024-05-01T10:00:00Z",
                "due_date": "2024-05-15T10:00:00Z",
                "returned_at": None,
                "status": "borrowed",
                "fine": 0.0
            }
        }


class OverdueLoan(BaseModel):
    """Overdue loan record"""
    loan_id: str
    user_id: str
    book_id: str
    user_name: str
    book_title: str
    due_date: datetime
    days_overdue: int
    fine: float

    class Config:
        json_schema_extra = {
            "example": {
                "loan_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "u123",
                "book_id": "b1",
                "user_name": "Alice Johnson",
                "book_title": "Learning Python",
                "due_date": "2024-05-15T10:00:00Z",
                "days_overdue": 5,
                "fine": 2.50
            }
        }


class FineRecord(BaseModel):
    """Fine record model"""
    fine_id: str
    user_id: str
    loan_id: str
    amount: float
    reason: str
    created_at: datetime
    paid: bool

    class Config:
        json_schema_extra = {
            "example": {
                "fine_id": "f123",
                "user_id": "u123",
                "loan_id": "loan123",
                "amount": 5.00,
                "reason": "Overdue by 10 days",
                "created_at": "2024-05-20T10:00:00Z",
                "paid": False
            }
        }


class StatsResponse(BaseModel):
    """API statistics response"""
    total_books: int
    total_users: int
    active_loans: int
    overdue_loans: int
    total_fines_pending: float

    class Config:
        json_schema_extra = {
            "example": {
                "total_books": 10,
                "total_users": 5,
                "active_loans": 8,
                "overdue_loans": 2,
                "total_fines_pending": 15.50
            }
        }


# Helper Functions
def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def seed_data() -> None:
    """Initialize database with sample data"""
    # Sample books
    books.update({
        "b1": {
            "id": "b1",
            "title": "Learning Python",
            "author": "Guido van Rossum",
            "category": "Programming",
            "available": 3,
            "total": 5,
            "isbn": "978-1491957592",
            "published_year": 2021
        },
        "b2": {
            "id": "b2",
            "title": "Python Cookbook",
            "author": "David Beazley",
            "category": "Programming",
            "available": 1,
            "total": 2,
            "isbn": "978-1491957660",
            "published_year": 2022
        },
        "b3": {
            "id": "b3",
            "title": "Introduction to Algorithms",
            "author": "Thomas H. Cormen",
            "category": "Computer Science",
            "available": 2,
            "total": 3,
            "isbn": "978-0262033848",
            "published_year": 2020
        },
        "b4": {
            "id": "b4",
            "title": "The Pragmatic Programmer",
            "author": "David Thomas",
            "category": "Programming",
            "available": 2,
            "total": 2,
            "isbn": "978-0201616224",
            "published_year": 2019
        },
        "b5": {
            "id": "b5",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "category": "Software Engineering",
            "available": 3,
            "total": 4,
            "isbn": "978-0132350884",
            "published_year": 2021
        }
    })

    # Sample users
    users.update({
        "u123": {
            "id": "u123",
            "name": "Alice Johnson",
            "email": "alice.johnson@example.com",
            "member_since": now_utc() - timedelta(days=365),
            "phone": "+1-555-0101",
            "active_loans": 0
        },
        "u456": {
            "id": "u456",
            "name": "Bob Smith",
            "email": "bob.smith@example.com",
            "member_since": now_utc() - timedelta(days=180),
            "phone": "+1-555-0102",
            "active_loans": 0
        },
        "u789": {
            "id": "u789",
            "name": "Charlie Brown",
            "email": "charlie.brown@example.com",
            "member_since": now_utc() - timedelta(days=90),
            "phone": "+1-555-0103",
            "active_loans": 0
        },
        "u999": {
            "id": "u999",
            "name": "Diana Prince",
            "email": "diana.prince@example.com",
            "member_since": now_utc() - timedelta(days=365),
            "phone": "+1-555-0104",
            "active_loans": 0
        }
    })

    logger.info("? Database seeded with sample data")


# Initialize data on startup
seed_data()


# Root Endpoint
@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to Limkokwing Library API",
        "version": "1.0.0",
        "documentation": "http://localhost:8000/docs",
        "status": "?? Running"
    }


# Books Endpoints
@app.get("/books", response_model=List[BookOut], tags=["Books"])
async def search_books(
    q: Optional[str] = Query(None, description="Search query"),
    field: Optional[str] = Query("title", description="Search field: title, author, or category"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Search for books by title, author, or category.
    
    **Query Parameters:**
    - `q`: Search term
    - `field`: Where to search (title, author, category)
    - `limit`: Maximum results (1-100)
    - `category`: Filter by specific category
    
    **Example:** `/books?q=python&field=title&category=Programming`
    """
    q_lower = q.lower() if q else None
    results = []
    
    for b in books.values():
        # Category filter
        if category and b["category"].lower() != category.lower():
            continue
            
        # If no search term, include all
        if not q_lower:
            results.append(b)
            continue
            
        # Search in specified field
        if field == "title" and q_lower in b["title"].lower():
            results.append(b)
        elif field == "author" and q_lower in b["author"].lower():
            results.append(b)
        elif field == "category" and q_lower in b["category"].lower():
            results.append(b)
    
    logger.info(f"Book search: query='{q}', field='{field}', results={len(results)}")
    return results[:limit]


@app.get("/books/{book_id}", response_model=BookOut, tags=["Books"])
async def get_book(book_id: str):
    """Get detailed information about a specific book"""
    if book_id not in books:
        logger.warning(f"Book not found: {book_id}")
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    
    return books[book_id]


@app.get("/books/category/{category}", response_model=List[BookOut], tags=["Books"])
async def get_books_by_category(category: str):
    """Get all books in a specific category"""
    results = [b for b in books.values() if b["category"].lower() == category.lower()]
    
    if not results:
        logger.warning(f"No books found in category: {category}")
        raise HTTPException(status_code=404, detail=f"No books found in category '{category}'")
    
    return results


# Users Endpoints
@app.get("/users", response_model=List[UserOut], tags=["Users"])
async def list_users():
    """Get list of all library members"""
    return [UserOut(**u) for u in users.values()]


@app.get("/users/{user_id}", response_model=UserOut, tags=["Users"])
async def get_user(user_id: str):
    """Get information about a specific user"""
    if user_id not in users:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    
    user = users[user_id]
    # Count active loans
    active_loans = sum(1 for loan in loans.values() 
                      if loan["user_id"] == user_id and loan["status"] == BorrowStatus.BORROWED)
    user["active_loans"] = active_loans
    
    return UserOut(**user)


# Borrow Endpoints
@app.post("/borrow", response_model=LoanRecord, tags=["Borrowing"])
async def borrow_book(req: BorrowRequest):
    """
    Borrow a book from the library.
    
    **Request Body:**
    - `user_id`: Valid user ID
    - `book_id`: Valid book ID
    - `days`: Duration (1-90 days)
    
    **Example:**
    ```json
    {
        "user_id": "u123",
        "book_id": "b1",
        "days": 14
    }
    ```
    """
    # Validate user
    if req.user_id not in users:
        logger.warning(f"Borrow failed: User not found - {req.user_id}")
        raise HTTPException(status_code=404, detail=f"User '{req.user_id}' not found")
    
    # Validate book
    if req.book_id not in books:
        logger.warning(f"Borrow failed: Book not found - {req.book_id}")
        raise HTTPException(status_code=404, detail=f"Book '{req.book_id}' not found")
    
    async with lock:
        book = books[req.book_id]
        user = users[req.user_id]
        
        # Check availability
        if book["available"] <= 0:
            logger.warning(f"Borrow failed: No copies available - {req.book_id}")
            raise HTTPException(status_code=400, detail=f"No copies of '{book['title']}' available")
        
        # Check for existing active loan
        existing_loan = next((l for l in loans.values() 
                            if l["user_id"] == req.user_id and 
                            l["book_id"] == req.book_id and 
                            l["status"] == BorrowStatus.BORROWED), None)
        
        if existing_loan:
            logger.warning(f"Borrow failed: User already has active loan - {req.user_id}, {req.book_id}")
            raise HTTPException(status_code=400, detail=f"User already has an active loan for this book")
        
        # Create loan record
        book["available"] -= 1
        loan_id = str(uuid.uuid4())
        borrowed_at = now_utc()
        due_date = borrowed_at + timedelta(days=req.days)
        
        record = {
            "loan_id": loan_id,
            "user_id": req.user_id,
            "book_id": req.book_id,
            "borrowed_at": borrowed_at,
            "due_date": due_date,
            "returned_at": None,
            "status": BorrowStatus.BORROWED,
            "fine": 0.0
        }
        
        loans[loan_id] = record
        user["active_loans"] = user.get("active_loans", 0) + 1
        
        logger.info(f"? Book borrowed: {req.user_id} borrowed {req.book_id} for {req.days} days")
        
        return LoanRecord(**record)


@app.post("/return", response_model=Dict[str, Any], tags=["Borrowing"])
async def return_book(req: ReturnRequest):
    """
    Return a borrowed book to the library.
    
    **Request Body:**
    - `user_id`: User ID
    - `book_id`: Book ID
    
    **Returns:** Loan details, return date, and fine (if overdue)
    
    **Example:**
    ```json
    {
        "user_id": "u123",
        "book_id": "b1"
    }
    ```
    """
    # Find active loan
    active_loan_id = None
    for lid, rec in loans.items():
        if (rec["user_id"] == req.user_id and 
            rec["book_id"] == req.book_id and 
            rec["status"] == BorrowStatus.BORROWED):
            active_loan_id = lid
            break
    
    if not active_loan_id:
        logger.warning(f"Return failed: No active loan found - {req.user_id}, {req.book_id}")
        raise HTTPException(status_code=404, detail="No active loan found for this user and book")
    
    async with lock:
        rec = loans[active_loan_id]
        returned_at = now_utc()
        rec["returned_at"] = returned_at
        rec["status"] = BorrowStatus.RETURNED
        
        # Update book availability
        books[req.book_id]["available"] += 1
        users[req.user_id]["active_loans"] = max(0, users[req.user_id].get("active_loans", 1) - 1)
        
        # Calculate fine if overdue
        days_overdue = (rec["returned_at"].date() - rec["due_date"].date()).days
        fine = round(max(0, days_overdue * FINE_PER_DAY), 2)
        
        rec["fine"] = fine
        
        # Record fine if applicable
        if fine > 0:
            fine_id = str(uuid.uuid4())
            fines[fine_id] = {
                "fine_id": fine_id,
                "user_id": req.user_id,
                "loan_id": active_loan_id,
                "amount": fine,
                "reason": f"Overdue by {days_overdue} day(s) @ ${FINE_PER_DAY}/day",
                "created_at": returned_at,
                "paid": False
            }
            logger.warning(f"? Fine issued: {req.user_id} - ${fine} (overdue by {days_overdue} days)")
        
        logger.info(f"? Book returned: {req.user_id} returned {req.book_id}, fine: ${fine}")
        
        return {
            "loan_id": active_loan_id,
            "status": rec["status"],
            "returned_at": rec["returned_at"],
            "due_date": rec["due_date"],
            "days_overdue": max(0, days_overdue),
            "fine": fine,
            "message": f"Book returned successfully. Fine: ${fine}" if fine > 0 else "Book returned successfully!"
        }


# Loan Management Endpoints
@app.get("/loans", response_model=List[LoanRecord], tags=["Loans"])
async def get_all_loans(status: Optional[str] = Query(None, description="Filter by status")):
    """Get all loans, optionally filtered by status (borrowed, returned, overdue)"""
    result = list(loans.values())
    
    if status:
        result = [l for l in result if l["status"].lower() == status.lower()]
    
    return [LoanRecord(**l) for l in result]


@app.get("/loans/user/{user_id}", response_model=List[LoanRecord], tags=["Loans"])
async def get_user_loans(user_id: str, status: Optional[str] = Query(None)):
    """Get all loans for a specific user"""
    if user_id not in users:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    
    result = [l for l in loans.values() if l["user_id"] == user_id]
    
    if status:
        result = [l for l in result if l["status"].lower() == status.lower()]
    
    return [LoanRecord(**l) for l in result]


@app.get("/loans/overdue", response_model=List[OverdueLoan], tags=["Loans"])
async def get_overdue_loans(user_id: Optional[str] = Query(None, description="Filter by user ID")):
    """
    Get all overdue loans.
    
    **Query Parameters:**
    - `user_id` (optional): Filter by specific user
    
    **Example:** `/loans/overdue?user_id=u123`
    """
    result = []
    today = now_utc().date()
    
    for rec in loans.values():
        if rec["status"] != BorrowStatus.BORROWED:
            continue
        
        if user_id and rec["user_id"] != user_id:
            continue
        
        due = rec["due_date"].date()
        
        if today > due:
            days_overdue = (today - due).days
            fine = round(days_overdue * FINE_PER_DAY, 2)
            
            overdue_record = OverdueLoan(
                loan_id=rec["loan_id"],
                user_id=rec["user_id"],
                book_id=rec["book_id"],
                user_name=users[rec["user_id"]]["name"],
                book_title=books[rec["book_id"]]["title"],
                due_date=rec["due_date"],
                days_overdue=days_overdue,
                fine=fine
            )
            result.append(overdue_record)
    
    logger.info(f"Overdue loans check: {len(result)} overdue items found")
    return result


@app.get("/loans/{loan_id}", response_model=LoanRecord, tags=["Loans"])
async def get_loan_details(loan_id: str):
    """Get detailed information about a specific loan"""
    if loan_id not in loans:
        raise HTTPException(status_code=404, detail=f"Loan '{loan_id}' not found")
    
    return LoanRecord(**loans[loan_id])


# Fine Management Endpoints
@app.get("/fines", response_model=List[FineRecord], tags=["Fines"])
async def get_all_fines(paid: Optional[bool] = Query(None, description="Filter by payment status")):
    """Get all fines, optionally filtered by payment status"""
    result = list(fines.values())
    
    if paid is not None:
        result = [f for f in result if f["paid"] == paid]
    
    logger.info(f"Fines retrieved: {len(result)} fines found")
    return result


@app.get("/fines/user/{user_id}", response_model=List[FineRecord], tags=["Fines"])
async def get_user_fines(user_id: str, paid: Optional[bool] = Query(None)):
    """Get all fines for a specific user"""
    if user_id not in users:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    
    result = [f for f in fines.values() if f["user_id"] == user_id]
    
    if paid is not None:
        result = [f for f in result if f["paid"] == paid]
    
    return result


@app.post("/fines/{fine_id}/pay", tags=["Fines"])
async def pay_fine(fine_id: str):
    """Mark a fine as paid"""
    if fine_id not in fines:
        raise HTTPException(status_code=404, detail=f"Fine '{fine_id}' not found")
    
    fine = fines[fine_id]
    
    if fine["paid"]:
        raise HTTPException(status_code=400, detail="Fine is already paid")
    
    fine["paid"] = True
    logger.info(f"? Fine paid: {fine_id} - ${fine['amount']}")
    
    return {"message": f"Fine of ${fine['amount']} marked as paid", "fine_id": fine_id}


# Statistics and Reports Endpoints
@app.get("/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_statistics():
    """Get library statistics and metrics"""
    total_books = len(books)
    total_users = len(users)
    active_loans_count = sum(1 for l in loans.values() if l["status"] == BorrowStatus.BORROWED)
    overdue_loans_count = sum(1 for l in loans.values() 
                             if l["status"] == BorrowStatus.BORROWED and 
                             l["due_date"].date() < now_utc().date())
    total_pending_fines = sum(f["amount"] for f in fines.values() if not f["paid"])
    
    return StatsResponse(
        total_books=total_books,
        total_users=total_users,
        active_loans=active_loans_count,
        overdue_loans=overdue_loans_count,
        total_fines_pending=total_pending_fines
    )


@app.get("/report/user-activity", tags=["Reports"])
async def user_activity_report():
    """Generate user activity report"""
    report = {
        "generated_at": now_utc().isoformat(),
        "users_activity": []
    }
    
    for user_id, user in users.items():
        user_loans = [l for l in loans.values() if l["user_id"] == user_id]
        user_fines = [f for f in fines.values() if f["user_id"] == user_id]
        
        report["users_activity"].append({
            "user_id": user_id,
            "name": user["name"],
            "email": user["email"],
            "total_loans": len(user_loans),
            "active_loans": sum(1 for l in user_loans if l["status"] == BorrowStatus.BORROWED),
            "returned_loans": sum(1 for l in user_loans if l["status"] == BorrowStatus.RETURNED),
            "total_fines": sum(f["amount"] for f in user_fines),
            "paid_fines": sum(f["amount"] for f in user_fines if f["paid"]),
            "unpaid_fines": sum(f["amount"] for f in user_fines if not f["paid"])
        })
    
    logger.info("User activity report generated")
    return report


@app.get("/report/book-inventory", tags=["Reports"])
async def book_inventory_report():
    """Generate book inventory report"""
    report = {
        "generated_at": now_utc().isoformat(),
        "total_books": len(books),
        "total_copies": sum(b["total"] for b in books.values()),
        "available_copies": sum(b["available"] for b in books.values()),
        "borrowed_copies": sum(b["total"] - b["available"] for b in books.values()),
        "books": []
    }
    
    for book_id, book in books.items():
        borrowed_count = book["total"] - book["available"]
        report["books"].append({
            "id": book_id,
            "title": book["title"],
            "author": book["author"],
            "category": book["category"],
            "total": book["total"],
            "available": book["available"],
            "borrowed": borrowed_count,
            "utilization": f"{(borrowed_count / book['total'] * 100):.1f}%" if book["total"] > 0 else "0%"
        })
    
    logger.info("Book inventory report generated")
    return report


# Error Handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors"""
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={"detail": f"Validation error: {str(exc)}"}
    )


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": now_utc().isoformat(),
        "database": {
            "books": len(books),
            "users": len(users),
            "loans": len(loans),
            "fines": len(fines)
        }
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("?? Starting Limkokwing Library API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
