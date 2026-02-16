FROM python:3.12-alpine

RUN apk add --no-cache unrar
WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "./runner.py"]
