# WordPress MCP Server

Comprehensive WordPress and server management через Model Context Protocol (MCP).

## Возможности

- ✅ Управление постами (создание, обновление, удаление, публикация)
- ✅ Управление страницами
- ✅ Управление категориями и тегами
- ✅ Управление медиафайлами
- ✅ Управление пользователями
- ✅ Управление комментариями
- ✅ Получение информации о сайте
- ✅ Поддержка ChatGPT (через SSE/HTTP)
- ✅ Поддержка Antigravity (через stdio)

## Быстрый старт

### 1. Установка зависимостей

```bash
cd My_MCP
python -m pip install -r requirements.txt
```

### 2. Настройка

Откройте `mcp_server.py` и проверьте настройки:

```python
WORDPRESS_URL = "https://04travel.ru"
WORDPRESS_USERNAME = "oasis"
WORDPRESS_PASSWORD = "mfIk tKGA mJ0p gwSD KmkN N0Ve"
```

### 3. Запуск

**Для Antigravity (stdio):**
```bash
python mcp_server.py
```

**Для ChatGPT (HTTP):**
```bash
python mcp_server.py --http
```

**Для SSE:**
```bash
python mcp_server.py --sse
```

## Использование в Antigravity

Добавьте в `mcp_config.json`:

```json
{
  "mcpServers": {
    "wordpress": {
      "command": "python",
      "args": ["e:\\YandexDisk\\MCP\\MCP wordpress\\wordpress-mcp-server\\My_MCP\\mcp_server.py"],
      "env": {}
    }
  }
}
```

## Использование в ChatGPT

1. Запустите сервер с `--http`
2. Используйте Cloudflare Tunnel для HTTPS:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. В ChatGPT добавьте connector с полученным URL

## Доступные инструменты

### Посты
- `get_post` - Получить пост по ID или slug
- `create_post` - Создать новый пост
- `update_post` - Обновить пост
- `delete_post` - Удалить пост
- `get_posts` - Получить список постов
- `publish_post` - Опубликовать пост
- `unpublish_post` - Снять с публикации

### Страницы
- `get_page` - Получить страницу
- `create_page` - Создать страницу
- `update_page` - Обновить страницу
- `delete_page` - Удалить страницу

### Категории и теги
- `get_categories` - Получить категории
- `create_category` - Создать категорию
- `get_tags` - Получить теги
- `create_tag` - Создать тег

### Медиа
- `get_media` - Получить медиафайлы

### Пользователи
- `get_users` - Получить пользователей

### Комментарии
- `get_comments` - Получить комментарии
- `approve_comment` - Одобрить комментарий
- `delete_comment` - Удалить комментарий

### Информация
- `get_site_info` - Получить информацию о сайте

## Примеры использования

### Создать пост
```
Создай пост с заголовком "Новая статья" и содержанием "Это тестовая статья"
```

### Получить список постов
```
Покажи последние 5 постов
```

### Обновить пост
```
Обнови пост с ID 123, измени заголовок на "Обновленный заголовок"
```

## Архитектура

```
ChatGPT/Antigravity
       ↓
  MCP Protocol
       ↓
  FastMCP Server
       ↓
WordPress REST API
       ↓
WordPress Site
```

## Безопасность

⚠️ **Важно:** Храните пароли в безопасности. Рекомендуется использовать Application Passwords вместо основного пароля.

## Логи

Все операции логируются в консоль с уровнем INFO.

## Разработка

Сервер построен на официальном MCP Python SDK с использованием FastMCP для упрощенной разработки.

## Лицензия

MIT
