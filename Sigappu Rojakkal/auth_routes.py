from flask import Blueprint, request, jsonify, session
from db import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    session.clear() 
    
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return {"success": False, "message": "Missing credentials"}, 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Query credentials table
            cursor.execute(
                "SELECT emp_id, password, is_admin FROM credentials WHERE username = %s LIMIT 1",
                (username,)
            )
            user = cursor.fetchone()

            if user and user['password'] == password:
                # Set session variables
                session['emp_code'] = user['emp_id']
                session['role'] = 'admin' if user['is_admin'] else 'employee'
                
                return {"success": True}, 200
            else:
                return {"success": False, "message": "Invalid credentials"}, 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
