from email.message import EmailMessage
import smtplib
import ssl


def send_link(settings,recipient,kind,raw_token):
    if not settings.smtp_host:return False
    message=EmailMessage();message['From']=settings.mail_from;message['To']=recipient
    action='Verify your email' if kind=='verify' else 'Reset your password'
    message['Subject']=action+' | Storylens'
    message.set_content(action+' using this link:\n\n'+settings.origin+'/account?action='+kind+'#token='+raw_token+'\n\nThis link expires in 30 minutes. If you did not request it, you can ignore this email.')
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        if settings.smtp_user:server.login(settings.smtp_user,settings.smtp_password)
        server.send_message(message)
    return True
