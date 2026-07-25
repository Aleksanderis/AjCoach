FROM docker/sandbox-templates:claude-code

USER root

# Add Python 3.12 + build tools
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*

# Seed cloudcli into a staging dir — copied to volume on first run
RUN npm install -g @cloudcli-ai/cloudcli --prefix /opt/cloudcli-seed

# Python venv for coach.py / garmin sync
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY project/requirements.txt /tmp/requirements.txt
RUN pip install --quiet -r /tmp/requirements.txt

# Entrypoint: seed cloudcli to volume on first run, then start
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh && chmod +x /entrypoint.sh

USER agent
WORKDIR /home/agent/AjCoach

# cloudcli lives in the mounted volume at /home/agent/.npm-global
ENV NPM_CONFIG_PREFIX=/home/agent/.npm-global
ENV PATH="/home/agent/.npm-global/bin:/opt/venv/bin:$PATH"
ENV HOST=0.0.0.0
ENV SERVER_PORT=3001
ENV HOME=/home/agent

EXPOSE 3001

ENTRYPOINT ["/entrypoint.sh"]
