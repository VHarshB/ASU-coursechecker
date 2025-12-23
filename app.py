from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import threading
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dsfovnqwksxlsusrcfil.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRzZm92bnF3a3N4bHN1c3JjZmlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU1Njk4NDQsImV4cCI6MjA4MTE0NTg0NH0.yJ5FwDyjxvweCl9yYaU_jtsEwO9v3NVgrdyhdgQ_YD8")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Global variables for monitoring
monitoring_active = False
last_check_time = None
check_thread = None

# Start monitoring automatically when the module is loaded
def start_monitoring():
    global monitoring_active, check_thread
    if not monitoring_active:
        monitoring_active = True
        check_thread = threading.Thread(target=monitoring_loop, daemon=True)
        check_thread.start()
        print("🚀 Course monitoring started in background")

# Start monitoring when the app is created
start_monitoring()
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=343&honors=F&keywords=Stefania%20Tracogna&promod=F&searchType=all&subject=MAT&term=2261", "course_number": "17645"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=343&honors=F&keywords=Stefania%20Tracogna&promod=F&searchType=all&subject=MAT&term=2261", "course_number": "22317"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=355&honors=F&keywords=%20Hani%20Ben%20Amor&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15428"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "10948"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15967"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15306"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15968"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "19648"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "25871"},
]

def save_to_supabase(course_number, result):
    """Save check result to Supabase"""
    try:
        data = {
            "course_number": course_number,
            "timestamp": result["timestamp"],
            "professor": result["professor"],
            "class_time": result["class_time"],
            "available_seats": result["available_seats"],
            "seats_text": result["seats_text"],
            "has_seats": result["has_seats"]
        }

        response = supabase.table("course_checker").insert(data).execute()
        print(f"✅ Saved to database: {course_number}")
        return True
    except Exception as e:
        print(f"❌ Failed to save to database: {e}")
        return False

def send_email(subject, body, to_email):
    try:
        sender_email = os.getenv("EMAIL_USER", "vaishyaharsh2003@gmail.com")
        sender_password = os.getenv("EMAIL_PASSWORD")

        if sender_password is None:
            print("⚠️ EMAIL_PASSWORD not set, skipping email")
            return

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def check_course_availability(url, course_number_to_search, max_retries=3):
    """Check availability for a single course"""
    driver = None
    for attempt in range(max_retries):
        try:
            print(f"🔍 Checking course {course_number_to_search}... (Attempt {attempt + 1}/{max_retries})")

            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Suppress logging
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(45)

            driver.get(url)
            time.sleep(3)

            # Wait for elements
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'class-results-rows'))
                )
            except:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="class-results"]'))
                )

            time.sleep(2)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            course_rows = soup.find_all('div', class_='class-results-cell number')

            if not course_rows:
                course_rows = soup.find_all('div', class_=lambda x: x and 'number' in x)

            if not course_rows:
                raise Exception("Could not find course listing elements")

            for row in course_rows:
                course_number_elem = row.find('div')
                if not course_number_elem:
                    continue

                course_number = course_number_elem.get_text(strip=True)

                if course_number == course_number_to_search:
                    instructor_cell = row.find_next_sibling('div', class_='instructor')
                    professor = instructor_cell.get_text(strip=True) if instructor_cell else "N/A"

                    days_cell = row.find_next_sibling('div', class_='days')
                    start_time_cell = row.find_next_sibling('div', class_='start')
                    end_time_cell = row.find_next_sibling('div', class_='end')
                    class_time = f"{days_cell.get_text(strip=True)} | {start_time_cell.get_text(strip=True)} - {end_time_cell.get_text(strip=True)}" if days_cell and start_time_cell and end_time_cell else "N/A"

                    seats_cell = row.find_next_sibling('div', class_='seats')
                    available_seats_text = seats_cell.get_text(strip=True) if seats_cell else "N/A"

                    available_seats_match = re.search(r'(\d+)', available_seats_text)
                    available_seats = int(available_seats_match.group(1)) if available_seats_match else 0

                    current_time = datetime.now().isoformat()

                    result = {
                        "timestamp": current_time,
                        "professor": professor,
                        "class_time": class_time,
                        "available_seats": available_seats,
                        "seats_text": available_seats_text,
                        "has_seats": available_seats > 0
                    }
                    save_to_supabase(course_number_to_search, result)

                    print(f"📚 Course Number: {course_number}")
                    print(f"👨‍🏫 Professor: {professor}")
                    print(f"🕐 Class Time: {class_time}")
                    print(f"💺 Available Seats: {available_seats_text}")

                    return available_seats > 0

            print(f"❌ Course {course_number_to_search} not found in results")

            result = {
                "timestamp": datetime.now().isoformat(),
                "professor": "N/A",
                "class_time": "N/A",
                "available_seats": 0,
                "seats_text": "Course not found",
                "has_seats": False
            }
            save_to_supabase(course_number_to_search, result)

            return False

        except Exception as e:
            print(f"❌ Error on attempt {attempt + 1}/{max_retries}: {str(e)}")
            if attempt < max_retries - 1:
                print("⏳ Retrying in 10 seconds...")
                time.sleep(10)
            else:
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "professor": "N/A",
                    "class_time": "N/A",
                    "available_seats": 0,
                    "seats_text": "Check failed",
                    "has_seats": False
                }
                save_to_supabase(course_number_to_search, result)
                return False
        finally:
            if driver:
                try:
                    driver.quit()
                    time.sleep(1)
                except:
                    pass

def monitoring_loop():
    """Background monitoring loop"""
    global monitoring_active, last_check_time

    print("🚀 Starting ASU Course Availability Checker...")
    print("📊 Monitoring courses every 2 minutes")
    print("☁️  Saving results to Supabase cloud database")

    consecutive_errors = 0
    max_consecutive_errors = 5

    while monitoring_active:
        try:
            print(f"🔄 Checking all courses... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            courses_checked = 0
            courses_with_errors = 0

            for course in courses_to_check:
                if not monitoring_active:
                    break

                try:
                    has_seats = check_course_availability(course["url"], course["course_number"])

                    if has_seats:
                        subject = f"🎉 Open Seats Available for Course {course['course_number']}"
                        body = f"Open seats are now available for course number {course['course_number']}!\n\n"
                        body += f"Course URL: {course['url']}\n\n"
                        body += f"Click the link above to register immediately."
                        to_email = os.getenv("NOTIFICATION_EMAIL", "hvaishya@asu.edu")

                        send_email(subject, body, to_email)
                        print(f"🚨 ALERT: Seats found for course {course['course_number']}!")
                    else:
                        print(f"😔 No seats available for course {course['course_number']}")

                    courses_checked += 1
                    consecutive_errors = 0
                    time.sleep(5)

                except Exception as e:
                    courses_with_errors += 1
                    print(f"⚠️ Error checking course {course['course_number']}: {str(e)}")
                    continue

            last_check_time = datetime.now()

            print(f"\n✅ Checked {courses_checked}/{len(courses_to_check)} courses successfully")
            if courses_with_errors > 0:
                print(f"⚠️ {courses_with_errors} courses had errors")

            print("⏱️  Waiting 2 minutes before next check...")
            print("=" * 60 + "\n")

            # Wait 2 minutes, but check every 10 seconds if monitoring should stop
            for _ in range(120):
                if not monitoring_active:
                    break
                time.sleep(1)

        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Unexpected error in main loop: {e}")
            print(f"⚠️ Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")

            if consecutive_errors >= max_consecutive_errors:
                print("❌ Too many consecutive errors. Stopping monitoring.")
                monitoring_active = False
                break

            print("⏳ Waiting 30 seconds before retry...")
            time.sleep(30)

    print("👋 Course checker stopped")

# Start monitoring when the app is created
start_monitoring()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/courses')
def get_courses():
    """Get current status of all courses"""
    try:
        # Get latest status for each course
        course_status = {}
        for course in courses_to_check:
            course_num = course["course_number"]
            try:
                # Get the most recent record from Supabase
                response = supabase.table("course_checker").select("*").eq("course_number", course_num).order("timestamp", desc=True).limit(1).execute()
                if response.data:
                    course_status[course_num] = response.data[0]
                else:
                    course_status[course_num] = {
                        "course_number": course_num,
                        "has_seats": False,
                        "available_seats": 0,
                        "seats_text": "No data",
                        "professor": "Unknown",
                        "class_time": "Unknown",
                        "timestamp": None
                    }
            except Exception as e:
                print(f"Error fetching data for course {course_num}: {e}")
                course_status[course_num] = {
                    "course_number": course_num,
                    "has_seats": False,
                    "available_seats": 0,
                    "seats_text": "Error",
                    "professor": "Unknown",
                    "class_time": "Unknown",
                    "timestamp": None
                }

        return jsonify({
            "success": True,
            "courses": course_status,
            "monitoring_active": monitoring_active,
            "last_check": last_check_time.isoformat() if last_check_time else None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/history/<course_number>')
def get_course_history(course_number):
    """Get history for a specific course"""
    try:
        response = supabase.table("course_checker").select("*").eq("course_number", course_number).order("timestamp", desc=True).limit(50).execute()
        return jsonify({"success": True, "history": response.data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/start-monitoring', methods=['POST'])
def start_monitoring():
    """Start the monitoring process"""
    global monitoring_active, check_thread

    if monitoring_active:
        return jsonify({"success": False, "message": "Monitoring already active"})

    monitoring_active = True
    check_thread = threading.Thread(target=monitoring_loop, daemon=True)
    check_thread.start()

    return jsonify({"success": True, "message": "Monitoring started"})

@app.route('/api/stop-monitoring', methods=['POST'])
def stop_monitoring():
    """Stop the monitoring process"""
    global monitoring_active

    monitoring_active = False
    return jsonify({"success": True, "message": "Monitoring stopped"})

@app.route('/api/status')
def get_status():
    """Get monitoring status"""
    return jsonify({
        "monitoring_active": monitoring_active,
        "last_check": last_check_time.isoformat() if last_check_time else None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)