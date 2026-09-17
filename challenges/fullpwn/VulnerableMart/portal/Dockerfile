# bullseye still ships wkhtmltopdf in-repo (trixie/bookworm removed it).
FROM python:3.9-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive

# wkhtmltopdf (Debian build needs an X server -> xvfb; xvfb-run needs xauth) +
# basic fonts, plus SSH/sudo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wkhtmltopdf xvfb xauth fontconfig fonts-dejavu-core \
        openssh-server sudo passwd curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*

# Real Chef Infra Client, falling back to cinc (binary-identical, reliable arm64
# Debian builds). Either way expose a stable /usr/local/bin/chef-apply and verify
# it actually executes on this arch.
RUN set -e; \
    (curl -fsSL https://omnitruck.chef.io/install.sh | bash -s -- -P chef) || true; \
    [ -x /opt/chef/bin/chef-apply ] && ln -sf /opt/chef/bin/chef-apply /usr/local/bin/chef-apply || true; \
    if ! /usr/local/bin/chef-apply --version >/dev/null 2>&1; then \
        (curl -fsSL https://omnitruck.cinc.sh/install.sh | bash -s -- -P cinc) || true; \
        [ -x /opt/cinc/bin/cinc-apply ] && ln -sf /opt/cinc/bin/cinc-apply /usr/local/bin/chef-apply || true; \
    fi; \
    /usr/local/bin/chef-apply --version || { echo 'ERROR: no working chef/cinc apply for this arch' >&2; exit 1; }

# Pre-accept the Chef license so the privesc is a clean `sudo chef-apply recipe.rb`
# (real Chef refuses to run otherwise; harmless no-op for the cinc fallback).
# chef-apply only takes --chef-license AFTER the recipe file.
RUN printf '# license bootstrap\n' > /tmp/accept.rb \
    && (/usr/local/bin/chef-apply /tmp/accept.rb --chef-license accept >/dev/null 2>&1 || true) \
    && rm -f /tmp/accept.rb \
    && ls /etc/chef/accepted_licenses/ 2>/dev/null || true

# Low-priv user. jdoe may run chef-apply as root (sudo, NOPASSWD) -> privesc.
RUN useradd -m -s /bin/bash jdoe \
    && echo 'jdoe ALL=(root) NOPASSWD: /usr/local/bin/chef-apply' > /etc/sudoers.d/jdoe-chef \
    && chmod 440 /etc/sudoers.d/jdoe-chef \
    && mkdir -p /run/sshd \
    && printf 'Port 50022\nPasswordAuthentication yes\nPermitRootLogin no\nUsePAM yes\n' \
        > /etc/ssh/sshd_config.d/ctf.conf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh

# 80 = portal web; 50022 = SSH (high port, port-scan target)
EXPOSE 80 50022

ENTRYPOINT ["/app/entrypoint.sh"]
