from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import uuid
from config import JWT_SECRET_KEY
from utils import store_session  # Import store_session from utils

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def generate_token(user_id, session_id):
    """
    Generate a JWT token containing the user_id and session_id.
    The token expires in 1 day.
    """
    payload = {
        "user_id": str(user_id),  # Convert ObjectId to string for JWT
        "session_id": session_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def verify_jwt_token(req):
    """Verify and decode JWT token from request headers; returns user_id if valid."""
    auth_header = req.headers.get("Authorization")
    if not auth_header:
        return None  # No token provided
    
    # Ensure the header is in the expected format
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None  # Improper header format
    
    token = parts[1]
    try:
        decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return decoded_token.get("user_id")
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Token invalid

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Registration endpoint:
      - Validates input.
      - Checks if a user with the provided email exists.
      - Hashes the password and stores the user.
    """
    from database.models import users_collection  # Ensure fresh import if needed

    if users_collection is None:
        return jsonify({"error": "Database connection error. Try again later."}), 500

    data = request.json
    user_name = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already exists"}), 409

    hashed_password = generate_password_hash(password)
    users_collection.insert_one({"username": user_name, "email": email, "password": hashed_password})

    return jsonify({"message": "User registered successfully!"}), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint:
      - Validates input.
      - Finds user by email.
      - Checks password hash.
      - Generates a unique session_id, stores the session, and returns a JWT token.
    """
    from database.models import users_collection  # Ensure proper import

    if users_collection is None:
        return jsonify({"error": "Database connection error. Please try again later."}), 500

    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found. Please register first."}), 404

    if not check_password_hash(user.get("password", ""), password):
        return jsonify({"error": "Invalid credentials"}), 401

    # Generate a unique session_id
    session_id = f"session_{user['_id']}_{uuid.uuid4()}"

    # Store the session in the database
    store_session(session_id, user["_id"])

    # Generate token with user_id and session_id
    token = generate_token(user["_id"], session_id)

    return jsonify({"message": "Login successful", "token": token}), 200

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint:
      - Validates the Authorization header.
      - Returns success message (JWT is stateless, so no server-side invalidation).
    """
    print("✅ Logout function called")  # Debugging statement

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header is missing"}), 400

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid Authorization header format. Expected 'Bearer <token>'"}), 400

    print("✅ Logout successful (Token not stored or blocked)")
    return jsonify({"message": "Logout successful"}), 200