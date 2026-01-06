import re
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

load_dotenv()

# Supabase configuration
SUPABASE_URL = "https://dsfovnqwksxlsusrcfil.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRzZm92bnF3a3N4bHN1c3JjZmlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU1Njk4NDQsImV4cCI6MjA4MTE0NTg0NH0.yJ5FwDyjxvweCl9yYaU_jtsEwO9v3NVgrdyhdgQ_YD8"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Thread-safe lock for email sending
email_lock = Lock()
db_lock = Lock()

def save_to_supabase(course_number, result):
    """Save check result to Supabase"""
    try:
        with db_lock:
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
        with email_lock:  # Ensure thread-safe email sending
            sender_email = "vaishyaharsh2003@gmail.com"
            sender_password = os.getenv("EMAIL_PASSWORD")

            if sender_password is None:
                raise ValueError("EMAIL_PASSWORD environment variable is not set.")

            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = to_email
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(message)

            print(f"✅ Email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def inspect_html_structure(url, course_number_to_search, max_retries=3):
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
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(20)

            driver.get(url)
            time.sleep(1)
            
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
                print(f"⚠️ No course rows found on page")
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
                    print(f"🕒 Checked at: {current_time}")
                    print("=" * 50)

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
                print(f"⏳ Retrying in 10 seconds...")
                time.sleep(10)
            else:
                print(f"❌ All retry attempts failed for course {course_number_to_search}")
                
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

def check_single_course(course):
    """Check a single course - designed to run in thread"""
    try:
        has_seats = inspect_html_structure(course["url"], course["course_number"])
        
        if has_seats:
            subject = f"🎉 Open Seats Available for Course {course['course_number']}"
            body = f"Open seats are now available for course number {course['course_number']}!\n\n"
            body += f"Course URL: {course['url']}\n\n"
            body += f"Click the link above to register immediately."
            to_emails = ["hvaishya@asu.edu", "sgill25@asu.edu"]
            
            for to_email in to_emails:
                send_email(subject, body, to_email)
            
            print(f"🚨 ALERT: Seats found for course {course['course_number']}!")
            return {"course": course['course_number'], "status": "seats_found", "error": None}
        else:
            print(f"😔 No seats available for course {course['course_number']}")
            return {"course": course['course_number'], "status": "no_seats", "error": None}
    
    except Exception as e:
        print(f"⚠️ Error checking course {course['course_number']}: {str(e)}")
        return {"course": course['course_number'], "status": "error", "error": str(e)}

def check_all_courses_concurrently(courses, max_workers=5):
    """Check all courses concurrently using ThreadPoolExecutor"""
    print(f"🚀 Starting concurrent check of {len(courses)} courses with {max_workers} workers...")
    
    results = {
        "checked": 0,
        "seats_found": 0,
        "errors": 0,
        "no_seats": 0
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_course = {executor.submit(check_single_course, course): course for course in courses}
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_course):
            result = future.result()
            results["checked"] += 1
            
            if result["status"] == "seats_found":
                results["seats_found"] += 1
            elif result["status"] == "error":
                results["errors"] += 1
            else:
                results["no_seats"] += 1
            
            print(f"📊 Progress: {results['checked']}/{len(courses)} courses checked")
    
    return results

courses_to_check = [
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=343&honors=F&keywords=Stefania%20Tracogna&promod=F&searchType=all&subject=MAT&term=2261", "course_number": "17645"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=343&honors=F&keywords=Stefania%20Tracogna&promod=F&searchType=all&subject=MAT&term=2261", "course_number": "22317"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=355&honors=F&keywords=%20Hani%20Ben%20Amor&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15428"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "10948"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15967"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15306"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "15968"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "19648"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=330&honors=F&keywords=Adil%20Ahmad&promod=F&searchType=all&subject=CSE&term=2261", "course_number": "25871"},
    {"url": "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=A&catalogNbr=212&honors=F&keywords=29662&promod=F&searchType=all&subject=ECN&term=2261", "course_number": "29662"},
]

def test_notifications():
    print("📧 Testing email notification...\n")
    
    test_course_number = "17645"
    test_url = "https://catalog.apps.asu.edu/catalog/classes/classlist?campusOrOnlineSelection=C&catalogNbr=343&honors=F&keywords=Stefania%20Tracogna&promod=F&searchType=all&subject=MAT&term=2261"
    
    subject = f"🧪 TEST: Open Seats Available for Course {test_course_number}"
    body = f"This is a TEST notification!\n\n"
    body += f"Open seats are now available for course number {test_course_number}!\n\n"
    body += f"Course URL: {test_url}\n\n"
    body += f"Click the link above to register immediately."
    to_emails = ["hvaishya@asu.edu", "sgill25@asu.edu"]
    for to_email in to_emails:
        send_email(subject, body, to_email)
    
    print("\n✅ Test email sent! Check your inbox.")
    print("📧 Email sent to: hvaishya@asu.edu, sgill25@asu.edu")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_notifications()
        sys.exit(0)
    
    print("🚀 Starting ASU Course Availability Checker (CONCURRENT MODE)...")
    print("📊 Monitoring courses every 30 seconds")
    print("☁️  Saving results to Supabase cloud database")
    print("⚡ Using multi-threading for faster checks")
    print("Press Ctrl+C to stop\n")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            start_time = time.time()
            print(f"🔄 Checking all courses concurrently... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check all courses concurrently (adjust max_workers based on your system)
            results = check_all_courses_concurrently(courses_to_check, max_workers=5)
            
            elapsed_time = time.time() - start_time
            
            print(f"\n✅ Completed in {elapsed_time:.2f} seconds")
            print(f"📊 Summary: {results['checked']} checked | {results['seats_found']} with seats | {results['no_seats']} no seats | {results['errors']} errors")
            
            consecutive_errors = 0
            
            print(f"⏱️  Waiting 30 seconds before next check...")
            print("=" * 60 + "\n")
            
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n👋 Course checker stopped by user")
            break
            
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Unexpected error in main loop: {e}")
            print(f"⚠️ Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"❌ Too many consecutive errors ({consecutive_errors}). Stopping script.")
                print("💡 Please check your internet connection and try again.")
                break
            
            print(f"⏳ Waiting 30 seconds before retry...")
            time.sleep(5)