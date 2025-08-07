from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from db import get_db_connection
import pandas as pd
import os
import random

# Import the necessary AI agent functions
from ai_agents import hr_agent_bulk_onboard, generate_employee_analysis_agent, profile_agent_get_vectors

# This creates the 'admin' blueprint.
admin_bp = Blueprint('admin', __name__)

# --- Page Rendering Routes ---

@admin_bp.route('/dashboard')
def dashboard_admin():
    """ Renders the main admin dashboard page. """
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('dashboard_admin.html')

@admin_bp.route('/management')
def management_page():
    """
    Renders the main, consolidated admin management page.
    """
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin_management.html')

@admin_bp.route('/agent_metrics')
def agent_metrics_page():
    """ Renders the agent metrics page. """
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin_agent_metrics.html')

@admin_bp.route('/ai_report/<int:emp_id>')
def ai_report_page(emp_id):
    """
    Generates and displays the AI-powered skill analysis report for a single employee.
    """
    if session.get('role') != 'admin':
        return redirect('/')
    
    employee_details, top_skills, weak_skills, analysis_text = generate_employee_analysis_agent(emp_id)
    
    if not employee_details:
        return "Employee not found", 404
        
    return render_template('admin_ai_report.html', 
                           employee=employee_details, 
                           top_skills=top_skills, 
                           weak_skills=weak_skills, 
                           analysis=analysis_text)

# --- API Endpoints for Admin Functionality ---

@admin_bp.route('/stats')
def get_dashboard_stats():
    """
    API endpoint to fetch statistics for the admin dashboard widgets.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_db_connection()
    stats = {
        "total_employees": 0,
        "learning_progress_chart": {"labels": [], "data": []},
        "course_status_chart": {"labels": [], "data": []}
    }
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(id) as total FROM employees")
            total_employees_result = cursor.fetchone()
            if total_employees_result:
                stats["total_employees"] = total_employees_result['total']

            cursor.execute("SELECT tr.role_name, COUNT(e.id) as employee_count FROM employees e JOIN tsr_roles tr ON e.tsr_role_id = tr.role_id GROUP BY tr.role_name")
            departments = cursor.fetchall()
            stats["learning_progress_chart"]["labels"] = [d['role_name'] for d in departments]
            stats["learning_progress_chart"]["data"] = [d['employee_count'] for d in departments]

            cursor.execute("SELECT status, COUNT(path_id) as count FROM learning_path GROUP BY status")
            course_statuses = cursor.fetchall()
            
            status_map = { "Completed": 0, "In Progress": 0, "Not Started": 0 }
            for row in course_statuses:
                if row['status'] in ['Passed', 'Completed']:
                    status_map['Completed'] += row['count']
                elif row['status'] == 'In Progress':
                    status_map['In Progress'] += row['count']
                else:
                    status_map['Not Started'] += row['count']
            
            stats["course_status_chart"]["labels"] = list(status_map.keys())
            stats["course_status_chart"]["data"] = list(status_map.values())

        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@admin_bp.route('/api/agent_metrics')
def get_agent_metrics():
    """
    API endpoint to fetch performance metrics for the AI agents.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    metrics = {
        "Recommender_Agent": {"queue": random.randint(0, 5), "latency_ms": random.randint(250, 600), "error_rate": f"{random.uniform(0.1, 1.5):.2f}%"},
        "Course_Content_Agent": {"queue": random.randint(0, 10), "latency_ms": random.randint(400, 900), "error_rate": f"{random.uniform(0.5, 2.5):.2f}%"},
        "Assessment_Agent": {"queue": random.randint(0, 3), "latency_ms": random.randint(300, 700), "error_rate": f"{random.uniform(0.2, 1.8):.2f}%"},
        "Tracker_Agent": {"queue": random.randint(0, 2), "latency_ms": random.randint(500, 1200), "error_rate": f"{random.uniform(1.0, 3.0):.2f}%"}
    }
    return jsonify({"success": True, "metrics": metrics})

@admin_bp.route('/api/profile_agent/<int:emp_id>')
def run_profile_agent(emp_id):
    """
    API endpoint to run the new Profile Agent for a specific employee.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    result = profile_agent_get_vectors(emp_id)
    if "error" in result:
        return jsonify({"success": False, "message": result.get("raw_response", result["error"])}), 500
        
    return jsonify({"success": True, "data": result})


@admin_bp.route('/employees', methods=['GET'])
def list_employees():
    """
    API endpoint to list all employees for the table in the admin panel.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT e.id, e.name, tr.role_name FROM employees e LEFT JOIN tsr_roles tr ON e.tsr_role_id = tr.role_id ORDER BY e.id"
            cursor.execute(sql)
            employees = cursor.fetchall()
        return jsonify({"success": True, "employees": employees})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@admin_bp.route('/employees', methods=['POST'])
def add_employee():
    """
    API endpoint for manually adding a single new employee.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql_employee = "INSERT INTO employees (name, html_score, css_score, javascript_score, python_score, java_score, c_score, cpp_score, sql_testing_score, tools_course_score, tsr_role_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql_employee, (data.get('Name'), data.get('HTML', 0), data.get('CSS', 0), data.get('JAVASCRIPT', 0), data.get('PYTHON', 0), data.get('JAVA', 0), data.get('C', 0), data.get('CPP', 0), data.get('SQL_TESTING', 0), data.get('TOOLS_COURSE', 0), 1))
            new_emp_id = cursor.lastrowid
            
            username = f"{data.get('Name').lower().replace(' ', '')}{new_emp_id}"
            sql_credentials = "INSERT INTO credentials (emp_id, username, password, is_admin) VALUES (%s, %s, %s, 0)"
            cursor.execute(sql_credentials, (new_emp_id, username, data.get('Password'),))
            
        conn.commit()
        return jsonify({"success": True, "message": "Employee added successfully!"})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@admin_bp.route('/employees/upload', methods=['POST'])
def upload_employees():
    """
    API endpoint for bulk-onboarding employees from a file upload.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400
        
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            return jsonify({"success": False, "message": "Unsupported file type"}), 400
            
        employees_added, error = hr_agent_bulk_onboard(df)
        
        if error:
            raise Exception(error)
            
        return jsonify({"success": True, "message": f"Successfully onboarded {employees_added} new employees."})

    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred: {e}"}), 500


@admin_bp.route('/employees/delete', methods=['POST'])
def delete_employee():
    """
    API endpoint to delete an employee record.
    """
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    emp_id = data.get('emp_id')
    if not emp_id:
        return jsonify({"success": False, "message": "Employee ID is required"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM credentials WHERE emp_id = %s", (emp_id,))
            cursor.execute("DELETE FROM learning_path WHERE emp_id = %s", (emp_id,))
            cursor.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Employee deleted successfully."})
        else:
            return jsonify({"success": False, "message": "Employee not found."}), 404
            
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()