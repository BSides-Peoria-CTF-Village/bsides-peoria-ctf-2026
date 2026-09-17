#!/bin/sh
set -e

# Flags into files. Root flag is root-only (forces the chef privesc); user flag is
# readable only by jdoe (the SSH foothold), NOT world-readable, so the PDF LFI
# (www-data) can't grab it without the SSH step.
printf '%s\n' "${ROOT_FLAG:-<ROOT_FLAG not set>}" > /root/root.txt
chmod 600 /root/root.txt
printf '%s\n' "${USER_FLAG:-<USER_FLAG not set>}" > /home/jdoe/user.txt
chown jdoe:jdoe /home/jdoe/user.txt
chmod 640 /home/jdoe/user.txt

# Set jdoe's SSH password.
if [ -n "$SSH_PASSWORD" ]; then
    echo "jdoe:$SSH_PASSWORD" | chpasswd
fi

# The mail that discloses the SSH password. World-readable (644) so the www-data
# PDF renderer's file:// LFI can include it.
mkdir -p /var/mail
cat > /var/mail/jdoe <<EOF
From: it-support@vulnmart.local
To: jdoe@vulnmart.local
Subject: Your SSH access is ready

Hi jdoe,

Your account on the invoicing host is provisioned. SSH in on port 50022:
  username: jdoe
  password: ${SSH_PASSWORD:-<unset>}

Please rotate this after your first login.
-- IT Support
EOF
chmod 644 /var/mail/jdoe

# Xvfb (used by wkhtmltopdf) needs this socket dir to exist and be world-writable.
mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# SSH host keys + daemon (background), then the portal app (as root, so it can
# drop the PDF renderer to www-data).
ssh-keygen -A >/dev/null 2>&1 || true
/usr/sbin/sshd

exec python app.py
