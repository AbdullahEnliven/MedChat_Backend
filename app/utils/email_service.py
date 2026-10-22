"""
Email Service
Send verification and password reset emails using Gmail SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")  # Your Gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Your Gmail App Password
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)
FROM_NAME = os.getenv("FROM_NAME", "MedChat Support")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")


def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send an email using Gmail SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text fallback (optional)
        
    Returns:
        True if email sent successfully, False otherwise
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("⚠️ Email not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        message["To"] = to_email
        
        # Add plain text version
        if text_content:
            part1 = MIMEText(text_content, "plain")
            message.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_content, "html")
        message.attach(part2)
        
        # Connect to Gmail SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Enable TLS encryption
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email to {to_email}: {str(e)}")
        return False


def send_verification_email(to_email: str, full_name: str, verification_token: str) -> bool:
    """
    Send email verification link to new user.
    
    Args:
        to_email: User's email address
        full_name: User's full name
        verification_token: Verification token
        
    Returns:
        True if sent successfully
    """
    verification_link = f"{APP_URL}/verify-email?token={verification_token}"
    
    subject = "Verify Your MedChat Account"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Welcome to MedChat!</h1>
            </div>
            <div class="content">
                <h2>Hi {full_name},</h2>
                <p>Thank you for signing up for MedChat! We're excited to have you on board.</p>
                <p>To complete your registration and start using MedChat, please verify your email address by clicking the button below:</p>
                <div style="text-align: center;">
                    <a href="{verification_link}" class="button">Verify Email Address</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="background: #fff; padding: 10px; border-radius: 5px; word-break: break-all;">{verification_link}</p>
                <p><strong>This verification link will expire in 48 hours.</strong></p>
                <p>If you didn't create a MedChat account, please ignore this email.</p>
                <div class="footer">
                    <p>© 2025 MedChat. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to MedChat!
    
    Hi {full_name},
    
    Thank you for signing up for MedChat!
    
    To verify your email address, please visit:
    {verification_link}
    
    This link will expire in 48 hours.
    
    If you didn't create a MedChat account, please ignore this email.
    
    © 2025 MedChat
    """
    
    return send_email(to_email, subject, html_content, text_content)


def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    """
    Send password reset link to user.
    
    Args:
        to_email: User's email address
        full_name: User's full name
        reset_token: Password reset token
        
    Returns:
        True if sent successfully
    """
    reset_link = f"{APP_URL}/reset-password?token={reset_token}"
    
    subject = "Reset Your MedChat Password"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <h2>Hi {full_name},</h2>
                <p>We received a request to reset your MedChat password.</p>
                <p>Click the button below to create a new password:</p>
                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="background: #fff; padding: 10px; border-radius: 5px; word-break: break-all;">{reset_link}</p>
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong><br>
                    This password reset link will expire in 24 hours.<br>
                    If you didn't request this reset, please ignore this email and your password will remain unchanged.
                </div>
                <div class="footer">
                    <p>© 2025 MedChat. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Reset Request
    
    Hi {full_name},
    
    We received a request to reset your MedChat password.
    
    To reset your password, please visit:
    {reset_link}
    
    This link will expire in 24 hours.
    
    If you didn't request this reset, please ignore this email.
    
    © 2025 MedChat
    """
    
    return send_email(to_email, subject, html_content, text_content)


def send_welcome_email(to_email: str, full_name: str) -> bool:
    """
    Send welcome email after successful verification.
    
    Args:
        to_email: User's email address
        full_name: User's full name
        
    Returns:
        True if sent successfully
    """
    subject = "Welcome to MedChat - Account Verified!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .feature {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #667eea; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to MedChat!</h1>
            </div>
            <div class="content">
                <h2>Hi {full_name},</h2>
                <p>Your account has been successfully verified! You can now access all MedChat features:</p>
                
                <div class="feature">
                    <strong>🧠 Smart Health Chat</strong><br>
                    Ask questions about health conditions, treatments, and medical advice
                </div>
                
                <div class="feature">
                    <strong>💊 Medicine Scanner</strong><br>
                    Take photos of medicines to get instant information
                </div>
                
                <div class="feature">
                    <strong>🤒 Symptom Checker</strong><br>
                    Check your symptoms and get potential diagnoses
                </div>
                
                <div class="feature">
                    <strong>📚 Health Tips</strong><br>
                    Get personalized daily health tips and advice
                </div>
                
                <div style="text-align: center;">
                    <a href="{APP_URL}" class="button">Start Using MedChat</a>
                </div>
                
                <p><strong>Remember:</strong> MedChat provides information for educational purposes only. Always consult with healthcare professionals for medical advice.</p>
                
                <div class="footer">
                    <p>© 2025 MedChat. All rights reserved.</p>
                    <p>Need help? Contact us at support@medchat.com</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to MedChat!
    
    Hi {full_name},
    
    Your account has been successfully verified!
    
    You can now access all MedChat features:
    - Smart Health Chat
    - Medicine Scanner
    - Symptom Checker
    - Health Tips
    
    Start using MedChat: {APP_URL}
    
    © 2025 MedChat
    """
    
    return send_email(to_email, subject, html_content, text_content)
