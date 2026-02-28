FROM python:3.11.3
COPY requirements.txt
RUN pip install -r requirements.txt
CMD python discordbot.py