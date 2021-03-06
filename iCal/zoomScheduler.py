from dotenv import load_dotenv
import json
import requests
import re
from icalendar import Calendar, Event
import tempfile, os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import COMMASPACE
from datetime import datetime

load_dotenv()


class ZoomScheduler:
    #TODO: JWT generation should come dynamically, not have a default in the .env file
    def __init__(self):
        self.zoom_key = os.getenv("ZOOM_API_KEY")
        self.email = os.getenv("ZOOM_EMAIL")
        self.JWT = os.getenv("ZOOM_JWT")
        self.smtp_email = os.getenv("SMTP_EMAIL")
        self.smtp_pass = os.getenv("SMTP_PWD")


    def send_invite(self, creation_details):
        URL = f"https://api.zoom.us/v2/users/{self.email}/meetings?access_token={self.JWT}"

        emails = self.get_details()
        data = {"myEmail" : self.email,
                "send_emails" : emails,
                "start" : creation_details["start_date"],
                "end" : creation_details["end_date"],
                "desc" : creation_details["desc"]
                }

        data = json.dumps(data, indent=4, sort_keys=True, default=str)
        headers = {
            "Content-Type":"application/json"
        }
        res = requests.post(URL, data=data, headers=headers)

        #to host
        cal = Calendar()
        cal.add_component(self.make_ical(data, res.content, "from"))
        dir = self.write_temp_dir(cal)
        data = json.loads(data)
        self.send_mail(dir, self.smtp_email, data["send_emails"], "MEETING INVITE!", data["desc"], "from")


        #to recipients
        unloaded_data = json.dumps(data)
        cal_2 = Calendar()
        cal_2.add_component(self.make_ical(unloaded_data, res.content, "to"))
        dir = self.write_temp_dir(cal_2)
        self.send_mail(dir, self.smtp_email, data["send_emails"], "MEETING INVITE!", data["desc"], "to")



    def get_details(self):
        to_send = input("Enter the email of the zoom participants, separated by a comma: ").split(",")
        emails = []
        for email in to_send:
            emails = self.check(email)
        return to_send

    def check(self, email):
        #regex for email
        regex = '^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$'
        if (re.search(regex, email.strip())):
            return email.strip()
        else:
            raise ValueError(f'Invalid email provided: {email}')

    def make_ical(self,data, zoom_details, type):
        event = Event()
        data = json.loads(data)
        zoom_data = json.loads(zoom_details)
        event.add("summary", data["desc"] )
        event.add("dtstart", datetime.strptime(data["start"], '%Y-%m-%d %H:%M:%S'))
        event.add('dtend', datetime.strptime(data["end"], '%Y-%m-%d %H:%M:%S'))
        if type=="from":
            event.add("description", zoom_data["start_url"])
        else:
            event.add("description", zoom_data["join_url"])
        for email in data["send_emails"]:
            event.add("attendee", f"MAILTO:${email}")



        return event


    def write_temp_dir(self, cal):
        directory = tempfile.mkdtemp()
        f = open(os.path.join(directory, 'invite.ics'), 'wb')
        f.write(cal.to_ical())
        f.close()
        return directory


    def send_mail(self, directory,send_from, send_to, subject, text, type):
        assert isinstance(send_to, list)

        # instance of MIMEMultipart
        msg = MIMEMultipart()

        # storing the senders email address
        msg['From'] = send_from

        # storing the receivers email address
        if type == "from":
            msg['To'] = COMMASPACE.join(send_to)
        else:
            msg["To"] = self.email

        # storing the subject
        msg['Subject'] = subject

        # string to store the body of the mail
        body = text

        # attach the body with the msg instance
        msg.attach(MIMEText(body, 'plain'))

        # open the file to be sent
        filename = "invite.ics"
        attachment = open(os.path.join(directory, filename), "rb")

        # instance of MIMEBase and named as p
        p = MIMEBase('application', 'octet-stream')

        # To change the payload into encoded form
        p.set_payload((attachment).read())

        # encode into base64
        encoders.encode_base64(p)

        p.add_header('Content-Disposition', "attachment; filename= %s" % filename)

        # attach the instance 'p' to instance 'msg'
        msg.attach(p)

        # creates SMTP session
        s = smtplib.SMTP('smtp.gmail.com', 587)

        # start TLS for security
        s.starttls()

        # Authentication
        s.login(send_from, self.smtp_pass)

        # Converts the Multipart msg into a string
        text = msg.as_string()

        # sending the mail
        s.sendmail(send_from, COMMASPACE.join(send_to), text)

        # terminating the session
        s.quit()
