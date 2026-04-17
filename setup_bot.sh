#!/bin/bash
set -e

echo "Оновлення системи..."
sudo apt-get update -y

echo "Встановлення Python 3, pip, Chromium та залежностей..."
sudo apt-get install python3 python3-pip python3-dev xvfb chromium-browser chromium-chromedriver -y

echo "Встановлення Python бібліотек глобально (без venv)..."
cd /home/ubuntu/iop-tracking-bot
sudo python3 -m pip install -r requirements.txt

echo "Створення systemd-сервісу iopbot.service..."
sudo bash -c 'cat <<EOF > /etc/systemd/system/iopbot.service
[Unit]
Description=IOP Tracking Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/iop-tracking-bot
ExecStart=/usr/bin/python3 /home/ubuntu/iop-tracking-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF'

echo "Запуск сервісу..."
sudo systemctl daemon-reload
sudo systemctl enable iopbot
sudo systemctl restart iopbot

echo "===== ГОТОВО! ====="
echo "Логи бота можна дивитися командою: journalctl -u iopbot -f -n 50"
