import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
import os


def send_hgt_email(smtp_conf, to_email, subject, body, pdf_bytes=None, pdf_name=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_conf["user"]
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8').encode()
        html = (f"<html><body style='font-family:Arial,sans-serif;color:#212a37;'>"
                f"<p>{body.replace(chr(10), '<br>')}</p></body></html>")
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        if pdf_bytes and pdf_name:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={pdf_name}')
            msg.attach(part)
        srv = smtplib.SMTP(smtp_conf["host"], smtp_conf["port"])
        srv.starttls()
        srv.login(smtp_conf["user"], smtp_conf["password"])
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        return str(e)
