from flask import Flask, render_template, session, redirect, url_for
from flask_cors import CORS
import os
from db import get_db_connection

# Import Blueprints
from auth_routes import auth_bp
from admin_routes import admin_bp
from employee_routes import employee_bp

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', 'a_very_secret_key')
CORS(app, supports_credentials=True)

# Register Blueprints for different parts of the application
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(employee_bp, url_prefix='/employee')


@app.route('/')
def home():
    """ Renders the main login page. """
    if session.get('role'):
        return redirect('/dashboard')
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """
    Central dashboard router.
    Redirects user to their specific dashboard based on the role in the session.
    """
    role = session.get('role')
    if role == 'admin':
        # The admin dashboard is now served from the blueprint
        return redirect(url_for('admin.dashboard_admin')) 
    elif role == 'employee':
        return redirect(url_for('employee.dashboard_employee'))
    # If no role or invalid role, send back to login
    return redirect(url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    """ Clears the session to log the user out. """
    session.clear()
    return {"success": True}

if __name__ == '__main__':
    app.run(debug=True, port=5000)