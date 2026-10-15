FROM python:3.11-slim

WORKDIR /app

# Set timezone to Asia/Ho_Chi_Minh
ENV TZ=Asia/Ho_Chi_Minh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run daemon mode by default (scheduled checks + Telegram listener)
CMD ["python", "main.py", "--daemon"]
