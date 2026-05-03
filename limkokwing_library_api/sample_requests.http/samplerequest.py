### GET all books
GET http://127.0.0.1:8000/books

### POST borrow
POST http://127.0.0.1:8000/borrow
Content-Type: application/json

{
  "user_id":"u123",
  "book_id":"b1",
  "days":14
}

### POST return
POST http://127.0.0.1:8000/return
Content-Type: application/json

{
  "user_id":"u123",
  "book_id":"b1"
}

### GET overdue
GET http://127.0.0.1:8000/loans/overdue
