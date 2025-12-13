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

load_dotenv()

# Supabase configuration
SUPABASE_URL = "https://dsfovnqwksxlsusrcfil.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRzZm92bnF3a3N4bHN1c3JjZmlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU1Njk4NDQsImV4cCI6MjA4MTE0NTg0NH0.yJ5FwDyjxvweCl9yYaU_jtsEwO9v3NVgrdyhdgQ_YD8"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def inspect_html_structure(url, course_number_to_search, max_retries=3):
    driver = None
    for attempt in range(max_retries):
        try:
            print(f"🔍 Checking course {course_number_to_search}... (Attempt {attempt + 1}/{max_retries})")
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)

            driver.get(url)

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'class-results-rows'))
            )

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            course_rows = soup.find_all('div', class_='class-results-cell number')

            for row in course_rows:
                course_number = row.find('div').get_text(strip=True)

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

                    # Save to Supabase
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

            print(f"❌ Course {course_number_to_search} not found")
            
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
            print(f"❌ Error on attempt {attempt + 1}/{max_retries} for course {course_number_to_search}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"⏳ Retrying in 5 seconds...")
                time.sleep(5)
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
                except:
                    pass

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
    to_email = "hvaishya@asu.edu"
    send_email(subject, body, to_email)
    
    print("\n✅ Test email sent! Check your inbox.")
    print("📧 Email sent to: hvaishya@asu.edu")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_notifications()
        sys.exit(0)
    
    print("🚀 Starting ASU Course Availability Checker...")
    print("📊 Monitoring courses every 2 minutes")
    print("☁️  Saving results to Supabase cloud database")
    print("Press Ctrl+C to stop\n")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            print(f"🔄 Checking all courses... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            courses_checked = 0
            courses_with_errors = 0
            
            for course in courses_to_check:
                try:
                    if inspect_html_structure(course["url"], course["course_number"]):
                        subject = f"🎉 Open Seats Available for Course {course['course_number']}"
                        body = f"Open seats are now available for course number {course['course_number']}!\n\n"
                        body += f"Course URL: {course['url']}\n\n"
                        body += f"Click the link above to register immediately."
                        to_email = "hvaishya@asu.edu"
                        
                        send_email(subject, body, to_email)
                        
                        print(f"🚨 ALERT: Seats found for course {course['course_number']}!")
                    else:
                        print(f"😔 No seats available for course {course['course_number']}")
                    
                    courses_checked += 1
                    consecutive_errors = 0
                    
                except Exception as e:
                    courses_with_errors += 1
                    print(f"⚠️ Error checking course {course['course_number']}: {str(e)}")
                    continue
            
            print(f"\n✅ Checked {courses_checked}/{len(courses_to_check)} courses successfully")
            if courses_with_errors > 0:
                print(f"⚠️ {courses_with_errors} courses had errors")
            
            print(f"⏱️  Waiting 2 minutes before next check...")
            print("=" * 60 + "\n")
            
            time.sleep(120)
            
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
            time.sleep(30)