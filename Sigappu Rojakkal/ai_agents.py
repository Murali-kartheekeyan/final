import os
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd
from db import get_db_connection
import random
import json

# Initialize the Language Model
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.5)

def call_ai(prompt: str):
    """Utility function to call the AI model and clean the response."""
    try:
        response = llm.invoke(prompt)
        clean_response = response.content.strip().replace("```json", "").replace("```", "").strip()
        return clean_response
    except Exception as e:
        return f'{{"error": "AI Error: {str(e)}"}}'

# --- NEW: Profile Agent for Inferring Skill Vectors ---
def profile_agent_get_vectors(emp_id: int):
    """
    Acts as a Profile Agent to analyze an employee's full history and infer
    latent skill vectors, as described in the provided image.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. GATHER INPUTS: HR/ERP data, past course completions, performance ratings
            # Using employee profile and initial scores as HR/ERP data
            cursor.execute("SELECT * FROM employees WHERE id = %s", (emp_id,))
            employee_profile = cursor.fetchone()
            if not employee_profile:
                return {"error": "Employee not found"}

            # Gathering past course completions
            cursor.execute("""
                SELECT c.course_name, lp.status
                FROM learning_path lp
                JOIN courses c ON lp.course_id = c.course_id
                WHERE lp.emp_id = %s AND lp.status IN ('Completed', 'Passed')
            """, (emp_id,))
            course_completions = cursor.fetchall()

            # Using assessment attempts as a proxy for performance/KPI scores
            cursor.execute("""
                SELECT c.course_name, aa.score, aa.passed
                FROM assessment_attempts aa
                JOIN learning_path lp ON aa.path_id = lp.path_id
                JOIN courses c ON lp.course_id = c.course_id
                WHERE lp.emp_id = %s
            """, (emp_id,))
            performance_ratings = cursor.fetchall()

        # 2. DEFINE PROCESS: Infer latent skills by correlating disparate data
        prompt = f"""
        You are an AI Profile Agent. Your task is to analyze an employee's comprehensive data to infer latent skill vectors and produce a structured profile.

        Here is the employee's disparate data:
        - HR Profile and Initial Scores: {employee_profile}
        - Course Completion History: {course_completions}
        - Performance Ratings (Assessment Scores): {performance_ratings}

        Based on this data, perform the following actions:
        1.  Correlate the employee's initial scores, the courses they completed, and their assessment performance to find patterns.
        2.  Infer latent skills. For example, if a user has high scores in 'Python' and 'SQL Testing' courses, infer a latent skill like 'Data Analysis'.
        3.  Produce the final output of "Employee skill vectors & history logs".

        Format your response as a single, clean JSON object with two keys:
        - "skill_vectors": An array of objects, where each object has "skill" and "level" (e.g., 'Novice', 'Intermediate', 'Advanced') keys.
        - "history_logs": An array of strings summarizing key milestones or observations.
        """

        # 3. GET OUTPUT: Call the AI and parse the response
        response_str = call_ai(prompt)
        try:
            return json.loads(response_str)
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response as JSON.", "raw_response": response_str}

    except Exception as e:
        return {"error": f"An error occurred during profile agent analysis: {str(e)}"}
    finally:
        if conn and conn.open:
            conn.close()


# --- Tracker Agent for Analyzing Learner Progress ---
def tracker_agent_analysis(emp_id: int):
    """
    Analyzes an employee's learning patterns, completion history, and quiz scores.
    Uses AI to detect plateaus and provide a summary.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Fetch course history
            cursor.execute("""
                SELECT c.course_name, lp.status, lp.progress 
                FROM learning_path lp
                JOIN courses c ON lp.course_id = c.course_id
                WHERE lp.emp_id = %s
            """, (emp_id,))
            course_history = cursor.fetchall()

            # Fetch assessment (quiz) history
            cursor.execute("""
                SELECT c.course_name, aa.score, aa.passed, aa.attempt_date
                FROM assessment_attempts aa
                JOIN learning_path lp ON aa.path_id = lp.path_id
                JOIN courses c ON lp.course_id = c.course_id
                WHERE lp.emp_id = %s
                ORDER BY aa.attempt_date DESC
            """, (emp_id,))
            assessment_history = cursor.fetchall()

        if not course_history and not assessment_history:
            return {"summary": "No learning activity found.", "details": "Start a course to begin tracking your progress."}

        # Use AI to analyze the data and generate a narrative
        prompt = f"""
        You are an AI Learning Tracker Agent. Your task is to analyze an employee's learning data and provide a concise, analytical summary.

        Here is the employee's data:
        - Course History: {course_history}
        - Assessment (Quiz) History: {assessment_history}

        Based on this data, please perform the following analysis:
        1.  **Overall Progress Summary:** Briefly summarize the employee's overall engagement and progress.
        2.  **Completion Patterns:** Analyze their course completion. Are they finishing courses they start? Is their progress consistent?
        3.  **Assessment Performance:** Look at their quiz scores. Are there multiple attempts on the same course (re-scores)? Do you see any patterns of plateauing (e.g., repeatedly failing the same assessment)?
        4.  **Actionable Insight:** Based on your analysis, provide one clear, encouraging insight or recommendation. For example, if they are plateauing, suggest a refresher; if they are doing well, encourage them to continue.

        Format your response as a simple JSON object with two keys: "summary" (a one-sentence headline) and "details" (a single string containing your full analysis with markdown for bolding and bullet points).
        """
        
        response_str = call_ai(prompt)
        try:
            return json.loads(response_str)
        except json.JSONDecodeError:
            return {"summary": "Analysis Complete", "details": response_str}

    except Exception as e:
        return {"summary": "Error", "details": f"An error occurred during analysis: {e}"}
    finally:
        if conn and conn.open:
            conn.close()


# --- Existing Admin-Facing Agents ---
def hr_agent_bulk_onboard(df: pd.DataFrame):
    conn = get_db_connection()
    employees_added = 0
    df.columns = [col.strip().upper() for col in df.columns]
    if 'NAME' not in df.columns: return 0, "File is missing the required 'NAME' column."
    try:
        with conn.cursor() as cursor:
            for _, row in df.iterrows():
                sql_employee = "INSERT INTO employees (name, html_score, css_score, javascript_score, python_score, java_score, c_score, cpp_score, sql_testing_score, tools_course_score, tsr_role_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(sql_employee, (
                    row.get('NAME'), row.get('HTML_SCORE', 0), row.get('CSS_SCORE', 0), row.get('JAVASCRIPT_SCORE', 0),
                    row.get('PYTHON_SCORE', 0), row.get('JAVA_SCORE', 0), row.get('C_SCORE', 0), row.get('CPP_SCORE', 0),
                    row.get('SQL_TESTING_SCORE', 0), row.get('TOOLS_COURSE_SCORE', 0), 1
                ))
                new_emp_id = cursor.lastrowid
                username = f"{row.get('NAME').lower().replace(' ', '')}{new_emp_id}"
                password = f"pass{new_emp_id}"
                sql_credentials = "INSERT INTO credentials (emp_id, username, password, is_admin) VALUES (%s, %s, %s, 0)"
                cursor.execute(sql_credentials, (new_emp_id, username, password))
                employees_added += 1
        conn.commit()
        return employees_added, None
    except Exception as e:
        conn.rollback()
        return 0, str(e)
    finally:
        conn.close()

def generate_employee_analysis_agent(emp_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT e.*, tr.role_name FROM employees e LEFT JOIN tsr_roles tr ON e.tsr_role_id = tr.role_id WHERE e.id = %s", (emp_id,))
            employee = cursor.fetchone()
            if not employee: return None, None, None, "Employee not found."
        skill_columns = {'HTML': 'html_score', 'CSS': 'css_score', 'JavaScript': 'javascript_score', 'Python': 'python_score', 'Java': 'java_score', 'C': 'c_score', 'C++': 'cpp_score', 'SQL Testing': 'sql_testing_score', 'Testing Tools': 'tools_course_score'}
        skills = {name: employee.get(col, 0) for name, col in skill_columns.items()}
        sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
        top_skills, weak_skills = dict(sorted_skills[:3]), dict(sorted_skills[-3:])
        employee_details = { "Name": employee.get('name'), "Role": employee.get('role_name') }
        prompt = f"You are an expert AI Career Development Analyst. Provide a concise, actionable upskilling roadmap. Employee Name: {employee_details['Name']}, TSR Role: {employee_details['Role']}, Full Skill Profile (Score out of 100): {skills}. Generate a report with markdown for: **Overall Summary**, **Key Strengths**, **Recommended Upskilling Roadmap**, and **Concluding Remark**."
        analysis_text = call_ai(prompt)
        return employee_details, top_skills, weak_skills, analysis_text
    except Exception as e:
        return None, None, None, f"An error occurred: {e}"
    finally:
        if conn and conn.open: conn.close()

# --- Existing Employee-Facing Agents ---
def recommender_agent_create_path(emp_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT e.*, tr.role_name FROM employees e LEFT JOIN tsr_roles tr ON e.tsr_role_id = tr.role_id WHERE e.id = %s", (emp_id,))
            employee = cursor.fetchone()
            if not employee: return {"success": False, "message": "Employee not found."}
            cursor.execute("SELECT s.skill_name, s.employee_score_column, tsr.required_proficiency FROM tsr_skill_requirements tsr JOIN skills s ON tsr.skill_id = s.skill_id WHERE tsr.role_id = %s", (employee['tsr_role_id'],))
            role_requirements = cursor.fetchall()
            skill_gaps = [{'skill_name': req['skill_name'], 'current_score': employee.get(req['employee_score_column'], 0), 'required_score': req['required_proficiency']} for req in role_requirements if employee.get(req['employee_score_column'], 0) < req['required_proficiency']]
            if not skill_gaps: return {"success": True, "path_exists": True, "message": "No skill gaps found!"}
            gap_skills_str = ", ".join([f"'{gap['skill_name']}'" for gap in skill_gaps])
            cursor.execute(f"SELECT c.course_id, c.course_name, s.skill_name FROM courses c JOIN skills s ON c.skill_id = s.skill_id WHERE s.skill_name IN ({gap_skills_str})")
            relevant_courses = cursor.fetchall()
            prompt = f"You are an AI Learning Path Designer. Create a personalized, ranked learning path for an employee based on their skill gaps. Employee Name: {employee['name']}, TSR Role: {employee['role_name']}, Skill Gaps: {skill_gaps}, Available Courses: {relevant_courses}. Instructions: Return ONLY a numbered list of the course names in the correct logical order."
            ai_ranked_list_str = call_ai(prompt)
            ranked_course_names = [line.split('. ')[1] for line in ai_ranked_list_str.split('\n') if '. ' in line]
            cursor.execute("DELETE FROM learning_path WHERE emp_id = %s", (emp_id,))
            for i, course_name in enumerate(ranked_course_names):
                course_id = next((c['course_id'] for c in relevant_courses if c['course_name'] == course_name), None)
                if course_id:
                    cursor.execute("INSERT INTO learning_path (emp_id, course_id, step_order) VALUES (%s, %s, %s)", (emp_id, course_id, i + 1))
            conn.commit()
            return {"success": True, "message": "A new learning path has been generated for you!"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()

def course_content_agent(course_name: str, slide_number: int, total_slides: int):
    prompt = f"You are an AI Instructional Designer. Generate content for slide {slide_number}/{total_slides} of the course \"{course_name}\". Return a JSON object with \"title\", \"image_url\" (using placehold.co), \"concept\", and \"example\"."
    response_str = call_ai(prompt)
    try:
        return json.loads(response_str)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response as JSON.", "raw_response": response_str}

def assessment_question_agent(course_name: str):
    prompt = f"You are an AI Quiz Generator. Create a 5-question multiple-choice quiz for the course \"{course_name}\". For each question, provide 4 options. Return ONLY a valid JSON array of objects. Each object must have: \"question\", \"options\", and \"correctAnswerIndex\"."
    response_str = call_ai(prompt)
    try:
        return json.loads(response_str)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response as JSON.", "raw_response": response_str}