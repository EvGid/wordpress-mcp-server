# Инструкция по установке на сервер

## Быстрая установка (один скрипт)

Скопируйте и выполните на сервере:

```bash
curl -sSL https://raw.githubusercontent.com/EvGid/wordpress-mcp-server/main/My_MCP/deploy.sh | bash
```

Или вручную:

```bash
# 1. Скачайте скрипт
wget https://raw.githubusercontent.com/EvGid/wordpress-mcp-server/main/My_MCP/deploy.sh

# 2. Сделайте исполняемым
chmod +x deploy.sh

# 3. Запустите
./deploy.sh
```

## Что делает скрипт

1. ✅ Обновляет систему
2. ✅ Устанавливает Python 3 и зависимости
3. ✅ Клонирует репозиторий в `/opt/wordpress-mcp-server`
4. ✅ Создает виртуальное окружение
5. ✅ Устанавливает Python пакеты
6. ✅ Тестирует подключение к WordPress
7. ✅ Создает systemd сервис
8. ✅ Запускает MCP сервер
9. ✅ Устанавливает Cloudflare Tunnel
10. ✅ Выдает HTTPS URL для ChatGPT

## Ручная установка (пошагово)

Если вы уже подключены к серверу через SSH:

### 1. Обновите систему
```bash
apt update && apt upgrade -y
```

### 2. Установите зависимости
```bash
apt install -y python3 python3-pip python3-venv git curl wget
```

### 3. Клонируйте репозиторий
```bash
mkdir -p /opt/wordpress-mcp-server
cd /opt/wordpress-mcp-server
git clone https://github.com/EvGid/wordpress-mcp-server.git .
cd My_MCP
```

### 4. Создайте виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. Установите пакеты
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Проверьте подключение
```bash
python test_server.py
```

### 7. Создайте systemd сервис
```bash
cat > /etc/systemd/system/wordpress-mcp.service <<'EOF'
[Unit]
Description=WordPress MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wordpress-mcp-server/My_MCP
Environment=PATH=/opt/wordpress-mcp-server/My_MCP/venv/bin
ExecStart=/opt/wordpress-mcp-server/My_MCP/venv/bin/python mcp_server.py --http
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### 8. Запустите сервис
```bash
systemctl daemon-reload
systemctl enable wordpress-mcp
systemctl start wordpress-mcp
systemctl status wordpress-mcp
```

### 9. Установите Cloudflare Tunnel
```bash
cd /root
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
```

### 10. Запустите туннель
```bash
nohup cloudflared tunnel --url http://localhost:8000 > /root/cloudflared.log 2>&1 &
sleep 5
cat /root/cloudflared.log | grep https://
```

## Управление сервером

### Проверить статус
```bash
systemctl status wordpress-mcp
```

### Просмотр логов
```bash
journalctl -u wordpress-mcp -f
```

### Перезапуск
```bash
systemctl restart wordpress-mcp
```

### Остановка
```bash
systemctl stop wordpress-mcp
```

### Cloudflare Tunnel логи
```bash
cat /root/cloudflared.log
```

### Получить HTTPS URL
```bash
grep -o 'https://[^ ]*' /root/cloudflared.log | head -1
```

## Устранение проблем

### Сервис не запускается
```bash
# Проверьте логи
journalctl -u wordpress-mcp -n 50

# Проверьте конфигурацию
cat /opt/wordpress-mcp-server/My_MCP/mcp_server.py | grep WORDPRESS_
```

### Cloudflare Tunnel не работает
```bash
# Перезапустите туннель
pkill cloudflared
nohup cloudflared tunnel --url http://localhost:8000 > /root/cloudflared.log 2>&1 &
```

### Обновление кода
```bash
cd /opt/wordpress-mcp-server
git pull origin main
systemctl restart wordpress-mcp
```
