FROM python:3.13-slim
ENV TZ=Europe/Madrid PYTHONUNBUFFERED=1
WORKDIR /app
COPY cableworld_epg.py .
RUN mkdir -p /data
EXPOSE 8080
CMD ["python", "cableworld_epg.py", "--serve", "-o", "/data/epg.xml"]
