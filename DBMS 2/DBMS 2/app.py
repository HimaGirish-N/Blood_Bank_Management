from flask import Flask, render_template, request, redirect, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "enterprise_secret_key" # Required for flash messages

# Connect to your NEW database
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Bhavan@123',
    'database': 'enterprise_bloodbank' 
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ==================== MAIN DASHBOARD ====================
@app.route('/')
def index():
    return render_template('index.html')

# ==================== DONOR MANAGEMENT ====================
@app.route('/add_donor', methods=['GET', 'POST'])
def add_donor():
    if request.method == 'POST':
        # 1. Fetch all Donor Attributes from the form
        d_id = request.form['donor_id']
        f_name = request.form['f_name']
        m_name = request.form.get('m_name', '') # Optional middle name
        l_name = request.form['l_name']
        gender = request.form['gender']
        age = int(request.form['age'])
        address = request.form['address']
        phone = request.form['phone']
        d_date = request.form['donation_date']
        h_cond = request.form['health_condition']
        
        # 2. Fetch Blood Attributes
        b_type = request.form['blood_group']
        blood_bank_id = 1 # Assuming linking to 'Central Red Cross' (BloodBankID 1)
        
        # Auto-generate a BloodID based on DonorID
        blood_id = int(d_id) + 50000 
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # FIX: Disable checks to resolve the Donor <-> Blood circular dependency
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # Step A: Insert Donor (Leaving BloodID NULL for a microsecond)
            cursor.execute("""
                INSERT INTO Donor (DonorID, F_Name, M_Name, L_Name, Gender, Age, Address, PhoneNumber, Donation_Date, Health_Condition) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (d_id, f_name, m_name, l_name, gender, age, address, phone, d_date, h_cond))
            
            # Step B: Insert the actual Blood Unit
            cursor.execute("""
                INSERT INTO Blood (BloodID, DonorID, BloodType, BloodBankID) 
                VALUES (%s, %s, %s, %s)
            """, (blood_id, d_id, b_type, blood_bank_id))
            
            # Step C: Update the Donor record with the newly created BloodID
            cursor.execute("UPDATE Donor SET BloodID = %s WHERE DonorID = %s", (blood_id, d_id))
            
            # Re-enable safety checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            flash("Enterprise Donor and Blood Unit registered successfully!", "success")
            
        except Exception as e:
            conn.rollback()
            flash(f"Database Error: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
            
        return redirect('/view_donors')
    
    return render_template('add_donor.html')

@app.route('/view_donors')
def view_donors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # JOIN Donor and Blood to display complete information
    query = """
        SELECT D.DonorID, D.F_Name, D.L_Name, D.Gender, D.Age, D.Health_Condition, D.Donation_Date, B.BloodType, B.BloodID 
        FROM Donor D
        LEFT JOIN Blood B ON D.BloodID = B.BloodID
    """
    cursor.execute(query)
    donors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('view_donors.html', donors=donors)

# ==================== PATIENT MANAGEMENT ====================
@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        p_id = request.form['patient_id']
        h_id = request.form['hospital_id']
        f_name = request.form['f_name']
        m_name = request.form.get('m_name', '')
        l_name = request.form['l_name']
        age = int(request.form['age'])
        gender = request.form['gender']
        address = request.form['address']
        phone = request.form['phone']
        b_type = request.form['blood_type']
        r_date = request.form['receive_date']
        blood_id = request.form['blood_id'] # The specific unit of blood they received
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Patient (PatientID, HospitalID, F_Name, M_Name, L_Name, Age, Gender, Address, PhoneNumber, BloodType, ReceiveDate, BloodID)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (p_id, h_id, f_name, m_name, l_name, age, gender, address, phone, b_type, r_date, blood_id))
            conn.commit()
            flash("Patient record added successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect('/view_patients')
        
    return render_template('add_patient.html')

@app.route('/view_patients')
def view_patients():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Patient")
    patients = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('view_patients.html', patients=patients)

# ==================== HOSPITAL ORDERS ====================
@app.route('/hospital_order', methods=['GET', 'POST'])
def hospital_order():
    if request.method == 'POST':
        order_no = request.form['order_no']
        h_id = request.form['hospital_id']
        qty = int(request.form['quantity'])
        b_type = request.form['blood_type']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Orders (OrderNo, HospitalID, Quantity, BloodType)
                VALUES (%s, %s, %s, %s)
            """, (order_no, h_id, qty, b_type))
            conn.commit()
            flash(f"Order #{order_no} placed successfully for {qty} units of {b_type} blood.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error placing order: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect('/hospital_order')
        
    return render_template('hospital_order.html')

# ==========================================================================
@app.route('/manage_inventory', methods=['GET', 'POST'])
def manage_inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST' and 'delete_expired' in request.form:
        try:
            # 1. Identify which Blood IDs are expired by JOINing with Donor
            cursor.execute("""
                SELECT B.BloodID FROM Blood B
                JOIN Donor D ON B.DonorID = D.DonorID
                WHERE D.Donation_Date < DATE_SUB(CURDATE(), INTERVAL 42 DAY)
            """)
            expired = cursor.fetchall()
            
            if expired:
                # Extract just the IDs into a tuple
                expired_ids = tuple([row['BloodID'] for row in expired])
                
                # Format string dynamically for the SQL IN clause based on how many units expired
                format_strings = ','.join(['%s'] * len(expired_ids))
                
                # 2. Disable constraints momentarily to break the circular dependency lock
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                
                # 3. Remove the BloodID from the Donor record (Sets to NULL instead of deleting the donor entirely)
                cursor.execute(f"UPDATE Donor SET BloodID = NULL WHERE BloodID IN ({format_strings})", expired_ids)
                
                # 4. Safely DELETE the actual expired blood units
                cursor.execute(f"DELETE FROM Blood WHERE BloodID IN ({format_strings})", expired_ids)
                deleted_count = cursor.rowcount
                
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.commit()
                flash(f"Success: {deleted_count} expired blood units (older than 42 days) were safely purged.", "success")
            else:
                flash("No expired blood units found. Inventory is fresh.", "primary")
                
        except Exception as e:
            conn.rollback()
            flash(f"Error during cleanup: {e}", "danger")

    # Fetch current inventory to display on the page
    cursor.execute("""
        SELECT B.BloodID, B.BloodType, D.F_Name, D.L_Name, D.Donation_Date 
        FROM Blood B 
        JOIN Donor D ON B.DonorID = D.DonorID
    """)
    inventory = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manage_inventory.html', inventory=inventory)

# ==================== ENTERPRISE DASHBOARD ====================
@app.route('/bloodbank_dashboard')
def bloodbank_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Complex query to show inventory count by Blood Type across the Blood Bank
    cursor.execute("""
        SELECT BloodType, COUNT(BloodID) as TotalUnits 
        FROM Blood 
        GROUP BY BloodType
    """)
    inventory = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('bloodbank_dashboard.html', inventory=inventory)

if __name__ == '__main__':
    app.run(debug=True)