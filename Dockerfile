FROM python:2-alpine

RUN apk add --no-cache unrar
WORKDIR /usr/src/app

COPY requirements.pip ./
RUN pip install --no-cache-dir -r requirements.pip

COPY . .

CMD [ "python", "./runner.py" ]
