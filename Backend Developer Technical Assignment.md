# Backend Developer — Technical Assignment

## Hotel Room Booking System

### Overview

Design and implement a simple hotel room booking system using Django.

The system should allow managing hotel rooms and creating bookings for specific time periods based on room features.

### 1. Room Management

Implement REST APIs to create, retrieve, update, and delete hotel rooms.

Each room should have the following attributes:

| Attribute | Description |
|---|---|
| ID | Unique identifier |
| Label | Unique room name or number |
| Number of beds | Integer between 1 and 5 |
| View | Sea, Mountain, or Yard |

### 2. Room Booking

Implement an API to book a room for a user.

The API receives:
- User identifier
- Requested room features (number of beds and view)
- Check-in datetime
- Check-out datetime

The system should automatically select an available room matching the requested criteria.

**Expected behavior:**
- If an appropriate room is available, create a booking and return the assigned room and booking details.
- A room cannot have overlapping bookings.

User management API is not required.

### 3. Deliverables

1. Create a **public GitHub repository** before starting development and use it throughout the project.
2. **Commit your work regularly**, following standard Git.
3. Include the following in the repository:
   - Complete source code and database migrations.
   - A README explaining how to set up and run the application.
   - A short explanation of important technical decisions and assumptions.
4. Once completed, **email the GitHub repository link** for review.

### 4. Time Expectation

We expect this assignment to take approximately 4–6 hours. Prioritize correctness and clarity over unnecessary features.

If you run out of time, document what remains incomplete and how you would approach it.

You are welcome to vibe code with AI agents and use AI assistants, documentation, and other development tools as part of your workflow. What matters is your ability to explain, validate, and modify all code you submit.