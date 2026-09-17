FROM python:3.9-slim

# iputils-ping for the (injectable) ping command; passwd provides useradd/usermod.
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping passwd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY maintenance.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 50050

ENTRYPOINT ["/app/entrypoint.sh"]
