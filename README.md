# WordPress MCP Server

Comprehensive WordPress management через Model Context Protocol (MCP).

## 🎯 Что это?

MCP сервер для полного управления WordPress сайтом через ChatGPT и Antigravity. Построен на официальном Python SDK (FastMCP).

## 📦 Две версии

### 1. **My_MCP** (Рекомендуется) - Новая версия на FastMCP
- ✅ Официальный MCP Python SDK
- ✅ 21 инструмент для управления WordPress
- ✅ Поддержка Antigravity (stdio)
- ✅ Поддержка ChatGPT (HTTP/SSE)
- ✅ Современная архитектура
- ✅ Полная документация

**Быстрый старт:**
```bash
cd My_MCP
python -m pip install -r requirements.txt
python test_server.py  # Проверка подключения
python mcp_server.py   # Запуск для Antigravity
```

[Подробная документация →](My_MCP/README.md)

### 2. **Legacy** - Оригинальная версия (SSE)
- Старая реализация с FastAPI
- Для ChatGPT через SSE
- Cloudflare Tunnel для HTTPS

## 🚀 Быстрый старт (My_MCP)

### 1. Установка

```bash
git clone https://github.com/EvGid/wordpress-mcp-server.git
cd wordpress-mcp-server/My_MCP
python -m pip install -r requirements.txt
```

### 2. Настройка

Откройте `mcp_server.py` и проверьте настройки:

```python
WORDPRESS_URL = "https://your-site.com"
WORDPRESS_USERNAME = "your-username"
WORDPRESS_PASSWORD = "your-app-password"
```

### 3. Тестирование

```bash
python test_server.py
```

### 4. Использование

**В Antigravity:**
- Следуйте инструкции в [ANTIGRAVITY_SETUP.md](My_MCP/ANTIGRAVITY_SETUP.md)

**В ChatGPT:**
```bash
python mcp_server.py --http
cloudflared tunnel --url http://localhost:8000
```

## 📚 Документация

- [My_MCP README](My_MCP/README.md) - Полная документация новой версии
- [Antigravity Setup](My_MCP/ANTIGRAVITY_SETUP.md) - Подключение к Antigravity
- [Legacy README](#legacy-version) - Документация старой версии

## 🛠️ Доступные инструменты (My_MCP)

### Посты (7 инструментов)
- `get_post`, `create_post`, `update_post`, `delete_post`
- `get_posts`, `publish_post`, `unpublish_post`

### Страницы (4 инструмента)
- `get_page`, `create_page`, `update_page`, `delete_page`

### Категории и теги (4 инструмента)
- `get_categories`, `create_category`, `get_tags`, `create_tag`

### Медиа, пользователи, комментарии (6 инструментов)
- `get_media`, `get_users`, `get_comments`, `approve_comment`, `delete_comment`, `get_site_info`

---

# Legacy Version

## Настройка WordPress credentials (Legacy)

**Вариант 1 (Рекомендуется): Использование .env файла**

Создайте файл `.env` в директории проекта:

```bash
cp .env.example .env
nano .env
```

Заполните значения:

```env
WORDPRESS_URL=https://your-wordpress-site.com/
WORDPRESS_USERNAME=your-username
WORDPRESS_PASSWORD=your-application-password
```

**Вариант 2: Прямое редактирование кода**

Откройте `mcp_sse_server.py` и измените значения по умолчанию (не рекомендуется для production):

```python
WORDPRESS_URL = "https://your-wordpress-site.com/"
WORDPRESS_USERNAME = "your-username"
WORDPRESS_PASSWORD = "your-password"
```
```

**Важно:** Используйте Application Password в WordPress (не основной пароль):
- WordPress Admin → Users → Your Profile → Application Passwords
- Создайте новый Application Password и используйте его

### 3. Запустите установку

```bash
chmod +x install.sh
sudo ./install.sh
```

Скрипт автоматически:

- Установит все зависимости
- Создаст виртуальное окружение Python
- Установит Python пакеты
- Создаст systemd сервис
- Запустит MCP сервер
- Установит Cloudflare Tunnel для HTTPS
- Выдаст HTTPS URL для подключения к ChatGPT

### 4. Подключите к ChatGPT

1. Откройте ChatGPT
2. Settings → Connectors → New Connector
3. Укажите:
   - **Name:** WordPress MCP
   - **URL:** `https://your-url.trycloudflare.com/sse` (из вывода install.sh)
   - **Authentication:** No authentication
4. Сохраните

### 5. Используйте!

Попросите ChatGPT:

```
Напиши статью про AI на 300 слов и опубликуй на моём WordPress сайте
```

## Архитектура

```
ChatGPT
  ↓ HTTPS/SSE
Cloudflare Tunnel
  ↓ HTTP
FastAPI MCP Server (port 8000)
  ↓ HTTPS
WordPress REST API
  ↓
WordPress Site
```

## Доступные инструменты

1. **create_post** - Создать новый пост
2. **update_post** - Обновить существующий пост
3. **get_posts** - Получить список постов
4. **delete_post** - Удалить пост

## Управление

### Проверка статуса

```bash
sudo systemctl status wordpress-mcp-server
```

### Просмотр логов

```bash
sudo journalctl -u wordpress-mcp-server -f
```

### Перезапуск

```bash
sudo systemctl restart wordpress-mcp-server
```

### Получить HTTPS URL

```bash
cat ~/cloudflared.log | grep "https://"
```

### Перезапустить Cloudflare Tunnel

```bash
pkill cloudflared
nohup cloudflared tunnel --url http://localhost:8000 > ~/cloudflared.log 2>&1 &
sleep 5
cat ~/cloudflared.log | grep "https://"
```

## Безопасность

⚠️ **Важно:**

1. Используйте Application Password в WordPress (не основной пароль)
2. Ограничьте доступ к серверу через firewall
3. Используйте HTTPS для WordPress API
4. Регулярно обновляйте зависимости

## Устранение неполадок

### Сервер не запускается

```bash
# Проверить логи
sudo journalctl -u wordpress-mcp-server -n 50

# Проверить конфигурацию
cat /opt/wordpress-mcp-server/mcp_sse_server.py | grep WORDPRESS
```

### Ошибки подключения к WordPress

1. Проверьте URL WordPress сайта
2. Убедитесь, что REST API включен
3. Проверьте credentials (username/password)
4. Проверьте, что Application Password создан в WordPress

### Cloudflare Tunnel не работает

```bash
# Проверить процесс
ps aux | grep cloudflared

# Перезапустить
pkill cloudflared
nohup cloudflared tunnel --url http://localhost:8000 > ~/cloudflared.log 2>&1 &
```

## Разработка

### Локальный запуск

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Запустить сервер
python mcp_sse_server.py
```

### Тестирование endpoints

```bash
# Health check
curl http://localhost:8000/health

# Server info
curl http://localhost:8000/

# MCP endpoint (initialize)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## Лицензия

MIT License

## Поддержка

При возникновении проблем:

1. Проверьте логи: `sudo journalctl -u wordpress-mcp-server -f`
2. Проверьте статус сервера: `sudo systemctl status wordpress-mcp-server`
3. Проверьте подключение к WordPress: `curl https://your-site.com/wp-json/wp/v2/posts`

