from flask import Flask, request, jsonify, session,render_template,redirect,flash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

db_config = {
    'host': "localhost",
    'user': "root",
    'password': "pass",
    'database': "world"
}


#logout endpoint
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return render_template("login.html")
#approve and reject application endpoint
#add max applicants,deadine,skills required
#professor-add areas of interest
#add skills to user
#make role,status etc enum
#project filter


def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                role ENUM('student', 'professor') NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                domain VARCHAR(255),
                status ENUM('open', 'closed') DEFAULT 'open',
                vacancies INT,
                deadline DATE,
                FOREIGN KEY(professor_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                project_id INT NOT NULL,
                resume TEXT NOT NULL,
                status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
                FOREIGN KEY(student_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        connection.commit()
        cursor.close()
        connection.close()

init_db()

@app.route('/')
def default():
    return render_template("login.html")


@app.route('/register')
def get_register():
    return render_template("register.html")

@app.route('/register', methods=['POST'])
def register():
    data = request.form  
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor()
    
    try:
        cursor.execute('INSERT INTO users (email, password, name, role) VALUES (%s, %s, %s, %s)',
                     (data['email'], data['password'], data.get('name'), data['role']))
        connection.commit()
        return redirect("/") 
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        connection.close()
       


@app.route('/login', methods=['POST'])
def login():
    data = request.form
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s',
                     (data['email'], data['password']))
        user = cursor.fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'error': 'Invalid credentials'}), 401
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        if user['role'] == 'professor':
            return redirect("/professor-dashboard")
        return redirect("/student-dashboard")

@app.route('/student-dashboard', methods=['GET'])
def student_dashboard():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)
    response = {}  

    try:
        cursor.execute('SELECT * FROM applications WHERE student_id= %s', (session['user_id'],))
        applications = cursor.fetchall()
        print(applications)
        accepted_projects=0
        accepted_projects_list={}
        pending_applications=0
        pending_projects_list={}
        # Get all projects
        cursor.execute('SELECT * FROM projects  where status="open"')
        projects = cursor.fetchall()
        if(len(applications)>0):
            accepted_applications_list = [app for app in applications if app['status'] == 'accepted']
            pending_applications_list = [app for app in applications if app['status'] == 'pending']

            accepted_projects = len(accepted_applications_list)
            pending_applications = len(pending_applications_list)

            accepted_project_ids = [app['project_id'] for app in accepted_applications_list]
            pending_project_ids = [app['project_id'] for app in pending_applications_list]

        

        # Filter projects based on accepted/pending status
            accepted_projects_list = [p for p in projects if p['id'] in accepted_project_ids]
            pending_projects_list = [p for p in projects if p['id'] in pending_project_ids]
        

        cursor.execute("SELECT name FROM users WHERE id= %s", (session['user_id'],))
        name_result = cursor.fetchone()
        student_name = name_result['name'] if name_result else 'Unknown'

        user = {
            'name': student_name,
            'accepted_projects': accepted_projects,
            'accepted_projects_list': accepted_projects_list,
            'pending_applications': pending_applications,
            'pending_projects_list': pending_projects_list
        }

        response = {
            'user': user,
            'available_projects': projects
        }

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

    return render_template("student_dashboard.html", response=response)

#correct this, accept/reject 
@app.route('/professor-dashboard', methods=['GET'])
def professor_dashboard():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Step 1: Get professor's projects
        cursor.execute("SELECT * FROM projects WHERE professor_id = %s", (session['user_id'],))
        professor_projects = cursor.fetchall()

        # Step 2: Get all applications for these projects
        applications = []
        project_ids = [p['id'] for p in professor_projects]

        for pid in project_ids:
            cursor.execute("SELECT * FROM applications WHERE project_id = %s", (pid,))
            apps = cursor.fetchall()
            applications.extend(apps)  # flatten the list

        # Step 3: Separate accepted and pending applications
        accepted_applications = [app for app in applications if app['status'] == 'accepted']
        pending_applications = [app for app in applications if app['status'] == 'pending']

        accepted_project_ids = list(set([app['project_id'] for app in accepted_applications]))
        pending_project_ids = list(set([app['project_id'] for app in pending_applications]))

        accepted_projects_list = [p for p in professor_projects if p['id'] in accepted_project_ids]
        pending_projects_list = [p for p in professor_projects if p['id'] in pending_project_ids]

        # Step 4: Get professor's name
        cursor.execute("SELECT name FROM users WHERE id = %s", (session['user_id'],))
        name_result = cursor.fetchone()
        professor_name = name_result['name'] if name_result else 'Unknown'

        # Step 5: Final response
        user = {
            'name': professor_name,
            'accepted_applications': len(accepted_projects_list),
            'accepted_applications_list': accepted_applications,
            'pending_applications': len(pending_applications),
            'pending_applications_list': pending_applications
        }

        response = {
            'user': user,
            'available_projects': professor_projects
        }

        return render_template("professor_dashboard.html", response=response)

    except Error as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        connection.close()


@app.route('/student/profile', methods=['GET'])
def student_profile():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute('SELECT * FROM projects WHERE id IN (SELECT project_id FROM applications WHERE student_id = %s and status="accepted") and status="closed"', (session['user_id'],))
        projects = cursor.fetchall()
        if projects:
            user['projects'] = projects
        else:   
            user['projects'] = []
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        return render_template("student_profile.html",user=user)

@app.route('/add-projects', methods=['GET'])
def add_projects():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    return render_template("add_project.html")
    

@app.route('/add-project', methods=['POST'])
def add_project():
    data = request.form
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor()
    
    try:
        if(session['role'] == 'professor'):
            cursor.execute('INSERT INTO projects (title, description, domain, deadline, vacancies, professor_id) VALUES (%s, %s, %s, %s, %s, %s)',
                     (data['project-title'], data['description'], data.get('role'), data['deadline'], data['vacancies'], session['user_id'],))
            connection.commit()
            return redirect("/professor-dashboard")
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        connection.close()


@app.route('/projects/search', methods=['GET'])
def search_projects():
    domain = request.args.get('domain')
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM projects WHERE domain = %s AND status = "open"', (domain,))
        projects = cursor.fetchall()
        return jsonify(projects), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/manage-projects', methods=['GET'])
def manage_projects():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute('SELECT * FROM projects WHERE professor_id = %s and status="open"', (session['user_id'],))
        projects = cursor.fetchall()
        print(projects)
        return render_template("manageProject.html", projects=projects)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
@app.route('/projects/<int:project_id>/apply', methods=['POST'])
def apply_to_project(project_id):
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor()
    try:
        cursor.execute('''
            SELECT * FROM applications 
            WHERE student_id = %s AND project_id = %s
        ''', (session['user_id'], project_id))
        existing_application = cursor.fetchone()

        if existing_application:
            return jsonify({'error': 'You have already applied for this project.'}), 400
        # Fetch resume from users table
        cursor.execute('SELECT resume_link FROM users WHERE id = %s', (session['user_id'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Resume not found'}), 404
        resume = result[0]

        # Insert application
        cursor.execute('''
            INSERT INTO applications (student_id, project_id, resume) 
            VALUES (%s, %s, %s)
        ''', (session['user_id'], project_id, resume))
        connection.commit()
        return redirect('/student-dashboard')
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        connection.close()

@app.route('/professor/profile', methods=['GET'])
def professor_profile():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        return render_template("professor_profile.html", user=user)
@app.route('/update-profile-prof', methods=['GET'])
def update_profile_prof():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        return render_template("update_profile_prof.html", user=user)
@app.route('/update-profile-student', methods=['GET', 'POST'])
def update_profile_student():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        skills = request.form.get('skills')
        resume_link = request.form.get('resume_link')

        try:
            # Try to add the columns if they don't exist (won't error if already there)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN skills TEXT")
            except mysql.connector.Error as e:
                if "Duplicate column name" not in str(e):
                    raise

            try:
                cursor.execute("ALTER TABLE users ADD COLUMN resume_link VARCHAR(255)")
            except mysql.connector.Error as e:
                if "Duplicate column name" not in str(e):
                    raise

        # Now update the values
            cursor.execute("""
                UPDATE users 
                SET name = %s, email = %s, skills = %s, resume_link = %s 
                WHERE id = %s
            """, (name, email, skills, resume_link, session['user_id']))
            connection.commit()
            flash('Profile updated successfully!')

        except Error as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            connection.close()
            return redirect('/student/profile')
    else:
        try:
            cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
        except Error as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            connection.close()
            return render_template("update_profile.html", user=user)



@app.route('/professor/projects', methods=['GET'])
def get_professor_projects():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM projects WHERE professor_id = %s', (session['user_id'],))
        projects = cursor.fetchall()
        return jsonify(projects), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
@app.route('/projects/<int:project_id>', methods=['GET'])
def view_project(project_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute('SELECT * FROM projects WHERE id = %s', (project_id,))
        project = cursor.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

    return render_template('project_view.html', project=project)

@app.route('/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor()
    
    try:
        cursor.execute('''
            UPDATE projects 
            SET title = %s, description = %s, domain = %s 
            WHERE id = %s AND professor_id = %s
        ''', (data.get('title'), data.get('description'), data.get('domain'), 
              project_id, session['user_id']))
        connection.commit()
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        return render_template("manageProject.html")

@app.route('/projects/<int:project_id>/close', methods=['POST'])
def close_project(project_id):
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor()
    
    try:
        cursor.execute('''
            UPDATE projects 
            SET status = "closed" 
            WHERE id = %s AND professor_id = %s
        ''', (project_id, session['user_id']))
        connection.commit()
        return redirect("/manage-projects")
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/professor/applications', methods=['GET'])
def get_applications():
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT a.* FROM applications a
            JOIN projects p ON a.project_id = p.id
            WHERE p.professor_id = %s AND a.status = 'pending'
        ''', (session['user_id'],))
        applications = cursor.fetchall()
        return jsonify(applications), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/applications/<int:application_id>/accept', methods=['POST'])
def accept_application(application_id):
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor()

    try:
        # Step 1: Fetch current status from DB
        cursor.execute('''
            SELECT a.status FROM applications a
            JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s AND p.professor_id = %s
        ''', (application_id, session['user_id']))
        row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Application not found or access denied'}), 404

        current_status = row[0]

        # Step 2: Determine new status (example: toggle status)
        new_status = 'accepted' if current_status == 'pending' else 'pending'

        # Step 3: Update application
        cursor.execute('''
            UPDATE applications 
            SET status = %s
            WHERE id = %s AND EXISTS (
                SELECT 1 FROM projects 
                WHERE id = applications.project_id AND professor_id = %s
            )
        ''', (new_status, application_id, session['user_id']))
        connection.commit()
        
        return redirect('/professor-dashboard')

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/applications/<int:application_id>/reject', methods=['POST'])
def reject_application(application_id):
    if 'user_id' not in session or session['role'] != 'professor':
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = connection.cursor()

    try:
        # Step 1: Fetch current status from DB
        cursor.execute('''
            SELECT a.status FROM applications a
            JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s AND p.professor_id = %s
        ''', (application_id, session['user_id']))
        row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Application not found or access denied'}), 404

        current_status = row[0]

        # Step 2: Determine new status (example: toggle status)
        new_status = 'rejected' if current_status == 'pending' else 'pending'

        # Step 3: Update application
        cursor.execute('''
            UPDATE applications 
            SET status = %s
            WHERE id = %s AND EXISTS (
                SELECT 1 FROM projects 
                WHERE id = applications.project_id AND professor_id = %s
            )
        ''', (new_status, application_id, session['user_id']))
        connection.commit()
        
        return redirect('/professor-dashboard')

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)