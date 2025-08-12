import smtplib
import io
import os
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional
from xhtml2pdf import pisa
from datetime import datetime
import socket
from dotenv import load_dotenv

load_dotenv()

# Use pypandoc-binary instead of pypandoc
try:
    import pypandoc
except ImportError:
    print("pypandoc-binary not found. Please install: pip install pypandoc-binary")
    raise

# Now these will load from your .env file
SENDER_EMAIL = os.getenv("GMAIL_USER")
SENDER_PASSWORD = os.getenv("GMAIL_PASSWORD")

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT_TLS = 587
SMTP_PORT_SSL = 465



# Basic CSS styles for PDF
PDF_STYLES = """
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 40px;
    color: #333;
    background-color: #fff;
}
h1 {
    color: #2c3e50;
    border-bottom: 3px solid #3498db;
    padding-bottom: 15px;
    margin-bottom: 30px;
    font-size: 28px;
}
h2 {
    color: #34495e;
    margin-top: 30px;
    margin-bottom: 15px;
    font-size: 22px;
}
h3 {
    color: #7f8c8d;
    margin-top: 20px;
    margin-bottom: 10px;
    font-size: 18px;
}
h4 {
    color: #95a5a6;
    margin-top: 15px;
    margin-bottom: 8px;
}
ul, ol {
    margin-left: 20px;
    margin-bottom: 15px;
}
li {
    margin-bottom: 8px;
    line-height: 1.5;
}
p {
    margin-bottom: 12px;
}
code {
    background-color: #f8f9fa;
    padding: 3px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 90%;
    color: #e74c3c;
}
pre {
    background-color: #f8f9fa;
    padding: 15px;
    border-radius: 5px;
    border-left: 4px solid #3498db;
    overflow-x: auto;
    margin: 15px 0;
}
blockquote {
    border-left: 4px solid #bdc3c7;
    margin: 15px 0;
    padding-left: 15px;
    color: #7f8c8d;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 15px 0;
}
th, td {
    border: 1px solid #ddd;
    padding: 12px;
    text-align: left;
}
th {
    background-color: #f2f2f2;
}
"""

def create_word_document(content: str, version: str) -> io.BytesIO:
    """
    Generates a properly formatted Word document using pypandoc-binary.
    """
    temp_filename = ""
    try:
        # Create a named temporary file that we can write to.
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_doc:
            temp_filename = temp_doc.name

        # Use pypandoc-binary to convert markdown to Word document
        pypandoc.convert_text(
            source=content,
            to='docx',
            format='md',
            outputfile=temp_filename,
            extra_args=[f'--metadata=title:Release Notes - {version}']
        )

        # Read the contents of the generated temporary file into a byte buffer.
        with open(temp_filename, 'rb') as f:
            bio = io.BytesIO(f.read())
        
        bio.seek(0)
        return bio

    except ImportError:
        raise Exception("Required library 'pypandoc-binary' not found. Please run: pip install pypandoc-binary")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during Word document generation: {e}")
    finally:
        # CRUCIAL: Clean up the temporary file from the disk.
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass  # Ignore cleanup errors

def create_pdf_document(content: str, version: str, styles: str) -> io.BytesIO:
    """Generates a PDF from markdown content using pypandoc-binary and xhtml2pdf."""
    try:
        # Convert markdown to HTML using pypandoc-binary
        html_body = pypandoc.convert_text(content, 'html', format='md')

        # Combine with a full HTML structure and CSS
        full_html = f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <style>{styles}</style>
            </head>
            <body>
                <h1>Release Notes - {version}</h1>
                {html_body}
            </body>
        </html>
        """
        
        bio = io.BytesIO()
        
        # Generate the PDF using xhtml2pdf
        pisa_status = pisa.CreatePDF(
            src=io.StringIO(full_html),
            dest=bio
        )

        if pisa_status.err:
            raise Exception(f"Failed to generate PDF: {pisa_status.err}")
        
        bio.seek(0)
        return bio
        
    except ImportError:
        raise Exception("Required libraries not found. Please run: pip install pypandoc-binary xhtml2pdf")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during PDF generation: {e}")

def send_email_with_gmail_fallback(msg, recipient_email):
    """Try multiple Gmail SMTP methods with fallback"""
    
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ Gmail credentials not configured!")
        return False
    
    # Clean password (remove any spaces)
    clean_password = SENDER_PASSWORD.replace(" ", "")
    
    methods = [
        {
            'name': 'Gmail SMTP with STARTTLS (Port 587)',
            'server': SMTP_SERVER,
            'port': SMTP_PORT_TLS,
            'use_ssl': False,
            'use_tls': True
        },
        {
            'name': 'Gmail SMTP_SSL (Port 465)',
            'server': SMTP_SERVER,
            'port': SMTP_PORT_SSL,
            'use_ssl': True,
            'use_tls': False
        }
    ]
    
    for method in methods:
        try:
            print(f"🔧 Trying {method['name']}...")
            
            # Create server connection
            if method['use_ssl']:
                server = smtplib.SMTP_SSL(method['server'], method['port'])
            else:
                server = smtplib.SMTP(method['server'], method['port'])
                if method['use_tls']:
                    server.starttls()
            
            # Login and send
            server.login(SENDER_EMAIL, clean_password)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
            server.quit()
            
            print(f"✅ Email sent successfully using {method['name']}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Authentication failed for {method['name']}: {e}")
            print("🔧 Check your Gmail app password and 2FA settings")
            
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error for {method['name']}: {e}")
            
        except Exception as e:
            print(f"❌ {method['name']} failed: {e}")
    
    print("❌ All Gmail methods failed!")
    return False

def send_success_email(result_object: Dict[str, Any], request_object) -> bool:
    """
    Send success email with PDF and Word attachments for successful release note generation.
    
    Args:
        result_object: Dictionary containing release note content and metadata
        request_object: ReleaseNoteRequest object containing user details
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate email configuration
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            print("❌ Gmail credentials not configured. Please set GMAIL_USER and GMAIL_PASSWORD.")
            return False
            
        # Extract information from objects
        user_name = request_object.created_by
        user_email = request_object.created_by_email
        release_tag = result_object["release_tag"]
        release_name = result_object.get("release_name", release_tag)
        content = result_object["release_note_content"]
        project_name = request_object.project_name
        
        print(f"📧 Preparing success email for {user_name} ({user_email})")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = user_email
        msg['Subject'] = f"✅ Release Notes Generated Successfully - {project_name} {release_tag}"
        
        # Email body
        body = f"""Dear {user_name},

Your release notes for {project_name} {release_name} have been generated successfully! 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 RELEASE DETAILS:
• Project: {project_name}
• Version: {release_tag}
• Release Name: {release_name}
• Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 SUMMARY:
• Total MRs in release: {result_object['documentation_summary']['mr_count']}
• Documented MRs: {result_object['documentation_summary']['documented_mr_count']}
• Model used: {result_object['llm_info']['model_used']}
• Input tokens: {result_object['llm_info']['input_tokens']:,}
• Output tokens: {result_object['llm_info']['output_tokens']:,}

📎 ATTACHMENTS:
The release notes are attached in both PDF and Word formats for your convenience.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Team CodeClarity

---
This is an automated message from the CodeClarity Release Notes Generator.
Generated with ❤️ for better documentation.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Generate and attach PDF
        attachments_added = 0
        try:
            print("📄 Generating PDF attachment...")
            pdf_buffer = create_pdf_document(content, release_tag, PDF_STYLES)
            pdf_attachment = MIMEBase('application', 'pdf')
            pdf_attachment.set_payload(pdf_buffer.getvalue())
            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="Release_Notes_{release_tag.replace("/", "_")}.pdf"'
            )
            msg.attach(pdf_attachment)
            attachments_added += 1
            print("✅ PDF attachment added successfully")
        except Exception as e:
            print(f"❌ Failed to attach PDF: {e}")
        
        # Generate and attach Word document
        try:
            print("📝 Generating Word document attachment...")
            word_buffer = create_word_document(content, release_tag)
            word_attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.wordprocessingml.document')
            word_attachment.set_payload(word_buffer.getvalue())
            encoders.encode_base64(word_attachment)
            word_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="Release_Notes_{release_tag.replace("/", "_")}.docx"'
            )
            msg.attach(word_attachment)
            attachments_added += 1
            print("✅ Word document attachment added successfully")
        except Exception as e:
            print(f"❌ Failed to attach Word document: {e}")
        
        print(f"📎 Total attachments: {attachments_added}/2")
        
        # Send email using fallback methods
        success = send_email_with_gmail_fallback(msg, user_email)
        
        if success:
            print(f"✅ Success email sent to {user_email}")
        else:
            print(f"❌ Failed to send success email to {user_email}")
            
        return success
        
    except Exception as e:
        print(f"❌ Unexpected error in send_success_email: {e}")
        return False

def send_failure_email(request_object, error_message: str) -> bool:
    """
    Send failure email when release note generation fails.
    
    Args:
        request_object: ReleaseNoteRequest object containing user details
        error_message: Specific error message describing the failure
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate email configuration
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            print("❌ Gmail credentials not configured. Please set GMAIL_USER and GMAIL_PASSWORD.")
            return False
            
        # Extract information from request object
        user_name = request_object.created_by
        user_email = request_object.created_by_email
        release_tag = request_object.release_tag
        project_name = request_object.project_name
        
        print(f"📧 Preparing failure email for {user_name} ({user_email})")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = user_email
        msg['Subject'] = f"❌ Release Notes Generation Failed - {project_name} {release_tag}"
        
        # Email body
        body = f"""Dear {user_name},

We encountered an issue while generating release notes for {project_name} {release_tag}. ⚠️

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 RELEASE DETAILS:
• Project: {project_name}
• Version: {release_tag}
• Target Branch: {request_object.target_branch}
• Previous Release: {request_object.previous_release_tag}
• Attempted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚨 ERROR DETAILS:
{error_message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 WHAT'S NEXT?
• Check your release configuration and try again
• Ensure all merge requests are properly documented
• Verify the target branch and previous release tag are correct
• Contact the development team if the issue persists

🔄 RETRY OPTIONS:
• Use the CodeClarity interface to retry generation
• Trigger the GitLab pipeline again
• Check GitLab CI/CD logs for more details

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Team CodeClarity

---
This is an automated message from the CodeClarity Release Notes Generator.
Need help? Please contact our support team or check the documentation.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email using fallback methods
        success = send_email_with_gmail_fallback(msg, user_email)
        
        if success:
            print(f"✅ Failure email sent to {user_email}")
        else:
            print(f"❌ Failed to send failure email to {user_email}")
            
        return success
        
    except Exception as e:
        print(f"❌ Unexpected error in send_failure_email: {e}")
        return False

def test_network_connectivity():
    """Test network connectivity to Gmail servers"""
    hosts_ports = [
        ('smtp.gmail.com', 587),
        ('smtp.gmail.com', 465),
        ('smtp.gmail.com', 25)
    ]
    
    print("🌐 Testing network connectivity to Gmail servers...")
    
    for host, port in hosts_ports:
        try:
            sock = socket.create_connection((host, port), timeout=10)
            sock.close()
            print(f"✅ {host}:{port} is reachable")
        except Exception as e:
            print(f"❌ {host}:{port} is blocked: {e}")

def test_gmail_authentication():
    """Test Gmail authentication with current credentials"""
    print("🔐 Testing Gmail authentication...")
    
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ Gmail credentials not configured!")
        print("Set environment variables:")
        print("export GMAIL_USER='tusharsoni142001.4@gmail.com'")
        print("export GMAIL_PASSWORD='your-16-char-app-password'")
        return False
    
    # Clean password
    clean_password = SENDER_PASSWORD.replace(" ", "")
    
    print(f"📧 Email: {SENDER_EMAIL}")
    print(f"🔑 Password length: {len(clean_password)} (should be 16)")
    print(f"🔑 Password preview: {clean_password[:4]}{'*' * max(0, len(clean_password)-4)}")
    
    # Test authentication methods
    methods = [
        {
            'name': 'SMTP with STARTTLS (587)',
            'func': lambda: smtplib.SMTP('smtp.gmail.com', 587),
            'use_tls': True
        },
        {
            'name': 'SMTP_SSL (465)',
            'func': lambda: smtplib.SMTP_SSL('smtp.gmail.com', 465),
            'use_tls': False
        }
    ]
    
    for method in methods:
        try:
            print(f"\n🔧 Testing {method['name']}...")
            server = method['func']()
            
            if method['use_tls']:
                server.starttls()
            
            server.login(SENDER_EMAIL, clean_password)
            server.quit()
            
            print(f"✅ {method['name']} authentication successful!")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            print("🔧 Check: 2FA enabled? App password correct?")
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
    
    return False

def send_test_email():
    """Send a simple test email to verify everything works"""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ Gmail credentials not configured!")
        return False
    
    try:
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = SENDER_EMAIL  # Send to yourself
        msg['Subject'] = "🧪 Gmail Test Email - CodeClarity"
        
        body = f"""This is a test email from CodeClarity Release Notes Generator.

📧 Sent from: {SENDER_EMAIL}
🕐 Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you receive this email, your Gmail configuration is working correctly! ✅

Best regards,
Team CodeClarity
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        success = send_email_with_gmail_fallback(msg, SENDER_EMAIL)
        
        if success:
            print(f"✅ Test email sent successfully to {SENDER_EMAIL}")
            print("📧 Check your inbox to confirm delivery!")
        else:
            print("❌ Test email failed")
            
        return success
        
    except Exception as e:
        print(f"❌ Test email error: {e}")
        return False

# Helper functions for easy integration
def handle_release_generation_success(result_object: Dict[str, Any], request_object):
    """Handle successful release note generation with email notification"""
    print("🎉 Release notes generated successfully!")
    email_sent = send_success_email(result_object, request_object)
    if email_sent:
        print("📧 Success notification sent successfully")
    else:
        print("📧 Failed to send success notification")
    return email_sent

def handle_release_generation_failure(request_object, error: Exception):
    """Handle failed release note generation with email notification"""
    print(f"❌ Release note generation failed: {error}")
    error_message = f"Error Type: {type(error).__name__}\n\nError Details:\n{str(error)}"
    email_sent = send_failure_email(request_object, error_message)
    if email_sent:
        print("📧 Failure notification sent successfully")
    else:
        print("📧 Failed to send failure notification")
    return email_sent

def run_complete_test():
    """Run complete Gmail setup test"""
    print("🚀 Running complete Gmail setup test...\n")
    
    # Step 1: Network connectivity
    test_network_connectivity()
    print()
    
    # Step 2: Gmail authentication
    auth_success = test_gmail_authentication()
    print()
    
    # Step 3: Send test email (only if authentication works)
    if auth_success:
        send_test_email()
    else:
        print("⚠️ Skipping test email due to authentication failure")
    
    print("\n🏁 Test complete!")

if __name__ == "__main__":
    # For testing - uncomment ONE of these methods:
    
    # Method 1: Set credentials directly for testing
    # SENDER_EMAIL = "tusharsoni142001.4@gmail.com"
    # SENDER_PASSWORD = "your-16-char-app-password-no-spaces"
    
    # Method 2: Use environment variables
    # Make sure to set: export GMAIL_USER="..." and export GMAIL_PASSWORD="..."
    
    # Run the complete test
    run_complete_test()