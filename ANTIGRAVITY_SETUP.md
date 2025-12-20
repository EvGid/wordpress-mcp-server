# Инструкция по подключению WordPress MCP к Antigravity

## Шаг 1: Найдите файл конфигурации

Файл `mcp_config.json` находится в одном из этих мест:

- `C:\Users\tux\.gemini\antigravity\mcp_config.json`
- `C:\Users\tux\AppData\Roaming\Cursor\User\globalStorage\mcp_config.json`

## Шаг 2: Откройте файл в редакторе

Используйте любой текстовый редактор (Notepad++, VS Code, или обычный Блокнот).

## Шаг 3: Добавьте конфигурацию WordPress MCP

Если файл пустой или содержит только `{}`, замените содержимое на:

```json
{
  "mcpServers": {
    "wordpress": {
      "command": "python",
      "args": [
        "e:\\YandexDisk\\MCP\\MCP wordpress\\wordpress-mcp-server\\My_MCP\\mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

Если в файле уже есть другие серверы, добавьте `"wordpress"` в секцию `"mcpServers"`:

```json
{
  "mcpServers": {
    "existing-server": {
      ...
    },
    "wordpress": {
      "command": "python",
      "args": [
        "e:\\YandexDisk\\MCP\\MCP wordpress\\wordpress-mcp-server\\My_MCP\\mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

## Шаг 4: Сохраните файл

Сохраните изменения и закройте редактор.

## Шаг 5: Перезапустите Antigravity

Полностью закройте и снова откройте Antigravity (Cursor AI).

## Шаг 6: Проверьте подключение

В Antigravity попробуйте команду:

```
Покажи последние 3 поста с моего WordPress сайта
```

Или:

```
Создай пост с заголовком "Тестовая статья" и содержанием "Это тест MCP сервера"
```

## Устранение проблем

### Проблема: "MCP server not found"

**Решение**: Проверьте путь к `mcp_server.py` в конфигурации. Убедитесь, что используются двойные обратные слеши `\\` или одинарные прямые `/`.

### Проблема: "Python not found"

**Решение**: Укажите полный путь к Python:

```json
{
  "mcpServers": {
    "wordpress": {
      "command": "C:\\Users\\tux\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
      "args": [
        "e:\\YandexDisk\\MCP\\MCP wordpress\\wordpress-mcp-server\\My_MCP\\mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

### Проблема: "Connection failed"

**Решение**: Запустите тест вручную:

```bash
cd "e:\YandexDisk\MCP\MCP wordpress\wordpress-mcp-server\My_MCP"
python test_server.py
```

Если тест проходит, проблема в конфигурации Antigravity.

## Готово!

После успешного подключения вы сможете управлять WordPress прямо из Antigravity.

### Примеры команд:

- "Создай пост про путешествия на Алтай"
- "Покажи все категории"
- "Обнови пост 123, добавь тег 'путешествия'"
- "Удали пост 456"
- "Покажи информацию о сайте"
