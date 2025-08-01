# utils/email_sender.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT_RAW = os.getenv("EMAIL_PORT", "587")
EMAIL_PORT = int(EMAIL_PORT_RAW.split('#')[0].strip())  # This line should now work

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "BWC Portal")

# --- NEW: Add debug prints for loaded ENV VARS ---
print(f"DEBUG_EMAIL_SENDER: Loaded ENV - HOST='{EMAIL_HOST}', PORT={EMAIL_PORT}, USER='{EMAIL_USERNAME}', SENDER_NAME='{EMAIL_SENDER_NAME}'")
# --- END NEW ---

def send_email(to_email: str, subject: str, body: str):
    # --- NEW: Debug print for send_email call ---
    print(f"DEBUG_EMAIL_SENDER: Attempting to send email to '{to_email}' with subject '{subject}'")
    # --- END NEW ---

    # Check if environment variables are missing (will skip if any are None)
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD]):
        print("Email sending skipped: Missing one or more email environment variables.")
        print("Please ensure EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD are set in your .env file.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_USERNAME}>"
    message["To"] = to_email

    # Attach body as plain text
    part1 = MIMEText(body, "plain")
    message.attach(part1)

    try:
        print("DEBUG_EMAIL_SENDER: Connecting to SMTP server...")  # <--- ADD THIS
        # Connect to SMTP server (TLS)
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()  # Secure the connection
        print("DEBUG_EMAIL_SENDER: Logging in to SMTP server...")  # <--- ADD THIS
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)  # Login to account
        print("DEBUG_EMAIL_SENDER: Sending email...")  # <--- ADD THIS
        server.sendmail(EMAIL_USERNAME, to_email, message.as_string())  # Send email
        server.quit()  # Close connection
        print(f"DEBUG_EMAIL_SENDER: Email sent successfully to {to_email}")  # <--- UPDATED LOG
        return True
    except Exception as e:
        print(f"DEBUG_EMAIL_SENDER: Failed to send email to {to_email}: {e}")  # <--- UPDATED LOG
        return False

# Example usage (for testing purposes, run this file directly)
if __name__ == "__main__":
    test_email = "thesrevma@gmail.com"  # Replace with an actual email for testing
    test_subject = "Test Email from BWC Portal"
    test_body = "This is a test email sent from your BWC Portal application."
    print(f"Attempting to send test email to {test_email}...")
    success = send_email(test_email, test_subject, test_body)
    print(f"Test email sent: {success}")