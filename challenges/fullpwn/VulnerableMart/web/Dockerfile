FROM python:3.9-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask && chmod +x entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/app/entrypoint.sh"]
