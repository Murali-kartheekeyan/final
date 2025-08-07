from flask import Blueprint, jsonify, request, session, render_template, redirect
from db import get_db_connection
# CORRECTED: Import the new tracker_agent_analysis function
from ai_agents import recommender_agent_create_path, course_content_agent, assessment_question_agent, tracker_agent_analysis
import json

employee_bp = Blueprint('employee', __name__)

# --- Learning Path and Dashboard Route ---

@employee_bp.route('/dashboard')
def dashboard_employee():
    """
    Renders the employee dashboard.
    This route calculates the real-time workflow status
    for the progress bar and passes it to the template.
    """
    if session.get('role') != 'employee':
        return redirect('/')

    emp_code = session.get('emp_code')
    employee_data = {}
    workflow_status = {
        "profile_loaded": True, # Always true if they are logged in
        "recommendations_generated": False,
        "learning_in_progress": False,
        "assessment_pending": False,
        "assessment_completed": False,
    }
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Fetch basic employee info
            cursor.execute("SELECT e.name, tr.role_name FROM employees e LEFT JOIN tsr_roles tr ON e.tsr_role_id = tr.role_id WHERE e.id = %s", (emp_code,))
            emp = cursor.fetchone()
            if emp:
                employee_data = { "name": emp.get('name'), "role": emp.get('role_name'), "department": "TSR-Based Role" }

            # Fetch learning path to determine workflow status
            cursor.execute("SELECT status FROM learning_path WHERE emp_id = %s", (emp_code,))
            path_steps = cursor.fetchall()

            if path_steps:
                workflow_status["recommendations_generated"] = True
                statuses = [step['status'] for step in path_steps]
                if 'In Progress' in statuses:
                    workflow_status["learning_in_progress"] = True
                # 'Completed' means course is done, assessment is next
                if 'Completed' in statuses or 'Failed' in statuses:
                    workflow_status["assessment_pending"] = True
                # 'Passed' means an assessment was completed successfully
                if 'Passed' in statuses:
                    workflow_status["assessment_completed"] = True

    finally:
        if conn and conn.open:
            conn.close()
        
    return render_template('dashboard_employee.html', employee=employee_data, workflow=workflow_status)


@employee_bp.route('/learning_path', methods=['GET', 'POST'])
def learning_path():
    if session.get('role') != 'employee': return jsonify({"success": False, "message": "Unauthorized"}), 401
    emp_id = session.get('emp_code')
    if request.method == 'POST':
        return jsonify(recommender_agent_create_path(emp_id))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT lp.path_id, lp.step_order, lp.status, lp.progress, c.course_name FROM learning_path lp JOIN courses c ON lp.course_id = c.course_id WHERE lp.emp_id = %s ORDER BY lp.step_order"
            cursor.execute(sql, (emp_id,))
            path = cursor.fetchall()
            return jsonify({"success": True, "path": path})
    finally:
        conn.close()

# --- Course Player Routes ---
@employee_bp.route('/course_player/<int:path_id>')
def course_player_page(path_id):
    if session.get('role') != 'employee': return redirect('/')
    # The total slides is hardcoded for this demonstration
    return render_template('course_player.html', path_id=path_id, total_slides=10)

@employee_bp.route('/get_slide_content', methods=['POST'])
def get_slide_content():
    if session.get('role') != 'employee': return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    path_id, slide_number, total_slides = data.get('path_id'), data.get('slide_number'), data.get('total_slides', 10)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT c.course_name FROM learning_path lp JOIN courses c ON lp.course_id = c.course_id WHERE lp.path_id = %s AND lp.emp_id = %s", (path_id, session.get('emp_code')))
            course = cursor.fetchone()
            if not course: return jsonify({"error": "Course not found"}), 404
        return jsonify(course_content_agent(course['course_name'], slide_number, total_slides))
    finally:
        conn.close()

@employee_bp.route('/update_progress', methods=['POST'])
def update_progress():
    if session.get('role') != 'employee': return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    path_id, progress = data.get('path_id'), data.get('progress')
    status = 'Completed' if progress >= 100 else 'In Progress'
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE learning_path SET progress = %s, status = %s WHERE path_id = %s AND emp_id = %s"
            cursor.execute(sql, (progress, status, path_id, session.get('emp_code')))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

# --- Assessment Page Routes ---
@employee_bp.route('/assessment')
def assessment_page():
    if session.get('role') != 'employee': return redirect('/')
    return render_template('assessment_page.html')

@employee_bp.route('/get_pending_assessments', methods=['GET'])
def get_pending_assessments():
    if session.get('role') != 'employee': return jsonify({"success": False, "message": "Unauthorized"}), 401
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT lp.path_id, c.course_name FROM learning_path lp JOIN courses c ON lp.course_id = c.course_id WHERE lp.emp_id = %s AND lp.status IN ('Completed', 'Failed') ORDER BY lp.step_order"
            cursor.execute(sql, (session.get('emp_code'),))
            assessments = cursor.fetchall()
            return jsonify({"success": True, "assessments": assessments})
    finally:
        conn.close()

@employee_bp.route('/get_assessment_questions', methods=['POST'])
def get_assessment_questions():
    if session.get('role') != 'employee': return jsonify({"error": "Unauthorized"}), 401
    course_name = request.json.get('course_name')
    if not course_name: return jsonify({"error": "Course name is required"}), 400
    questions = assessment_question_agent(course_name)
    return jsonify(questions)

@employee_bp.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    if session.get('role') != 'employee': return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    path_id, answers, questions = data.get('path_id'), data.get('answers'), data.get('questions')
    score = 0
    for i, q in enumerate(questions):
        # Ensure answers are compared as the same type (integer)
        if str(i) in answers and int(answers.get(str(i))) == q['correctAnswerIndex']:
            score += 1
    final_score = int((score / len(questions)) * 100)
    passed = 1 if final_score >= 70 else 0
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO assessment_attempts (path_id, score, passed) VALUES (%s, %s, %s)", (path_id, final_score, passed))
            new_status = 'Passed' if passed else 'Failed'
            message = f"You Passed with {final_score}%!" if passed else f"You scored {final_score}%. Please try again."
            cursor.execute("UPDATE learning_path SET status = %s WHERE path_id = %s", (new_status, path_id))
        conn.commit()
        return jsonify({"success": True, "message": message, "score": final_score})
    finally:
        conn.close()

# --- NEW: Tracker Agent Routes ---
@employee_bp.route('/tracker')
def tracker_page():
    """Renders the new Tracker Agent page."""
    if session.get('role') != 'employee':
        return redirect('/')
    return render_template('tracker_agent.html')

@employee_bp.route('/get_tracker_analysis', methods=['GET'])
def get_tracker_analysis():
    """API endpoint to get the AI-powered tracker analysis."""
    if session.get('role') != 'employee':
        return jsonify({"error": "Unauthorized"}), 401
    emp_id = session.get('emp_code')
    analysis = tracker_agent_analysis(emp_id)
    return jsonify(analysis)