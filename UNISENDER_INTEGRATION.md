# Интеграция с Unisender API

Интеграция с Unisender API для массовых email-рассылок реализована в модуле `unisender_client.py`.

## Настройка

1. Получите API ключ Unisender:
   - Войдите в личный кабинет: https://cp.unisender.com/ru/v5/user/info/api
   - Скопируйте ваш API ключ

2. Добавьте API ключ в переменные окружения:
   ```bash
   UNISENDER_API_KEY=your_unisender_api_key_here
   ```

3. Клиент автоматически инициализируется при запуске бота, если API ключ установлен.

## Использование

### Базовое использование

```python
from unisender_client import UnisenderClient

# Инициализация клиента
client = UnisenderClient(api_key="your_api_key")

# Отправка одиночного email
result = client.send_email(
    email="recipient@example.com",
    sender_name="Ваше Имя",
    sender_email="sender@example.com",
    subject="Тема письма",
    body="<h1>Привет!</h1><p>Это тестовое письмо.</p>"
)

print(result)
```

### Импорт контактов

```python
# Импорт контактов в список
contacts = [
    {"email": "user1@example.com", "Name": "Иван Иванов", "phone": "+79001234567"},
    {"email": "user2@example.com", "Name": "Петр Петров", "phone": "+79007654321"},
]

result = client.import_contacts(
    contacts=contacts,
    field_names=["email", "Name", "phone"],
    list_ids=[123],  # ID списка контактов
    override_lists=False
)

print(result)
```

### Подписка контакта на списки

```python
# Подписка контакта на списки
result = client.subscribe(
    email="user@example.com",
    list_ids=[123, 456],  # ID списков для подписки
    tags=["новый_клиент", "рассылка_1"],
    double_optin=False  # Использовать двойную подписку
)

print(result)
```

### Создание массовой рассылки

```python
# 1. Создать email сообщение
message_result = client.create_email_message(
    sender_name="Ваше Имя",
    sender_email="sender@example.com",
    subject="Массовая рассылка",
    body="<h1>Привет!</h1><p>Это массовая рассылка.</p>",
    list_id=123
)

message_id = message_result.get('result', {}).get('message_id')

# 2. Создать рассылку
campaign_result = client.create_campaign(
    message_id=message_id,
    list_id=123,
    start_time="2024-01-15 10:00:00"  # Опционально: время начала рассылки
)

campaign_id = campaign_result.get('result', {}).get('campaign_id')
print(f"Рассылка создана с ID: {campaign_id}")
```

### Получение списков контактов

```python
# Получить все списки контактов
lists = client.get_lists()
print(lists)
```

## Доступные методы

### sendEmail
Отправка одиночного email письма.

**Параметры:**
- `email` - Email адрес получателя (обязательно)
- `sender_name` - Имя отправителя (обязательно)
- `sender_email` - Email адрес отправителя (обязательно)
- `subject` - Тема письма (обязательно)
- `body` - Тело письма, HTML или текст (обязательно)
- `list_id` - ID списка контактов (опционально)
- `tags` - Список тегов для контакта (опционально)

**Документация:** https://www.unisender.com/ru/support/api/messages/sendemail/

### importContacts
Импорт контактов в списки.

**Параметры:**
- `contacts` - Список контактов, каждый контакт - словарь с полями (обязательно)
- `field_names` - Список названий полей (опционально, определяется автоматически)
- `list_ids` - ID списков для добавления контактов (опционально)
- `override_lists` - Если True, контакты будут добавлены только в указанные списки (опционально)

**Документация:** https://www.unisender.com/ru/support/api/contacts/importcontacts/

### subscribe
Подписка контакта на списки.

**Параметры:**
- `email` - Email адрес контакта (обязательно)
- `list_ids` - Список ID списков для подписки (обязательно)
- `tags` - Список тегов для контакта (опционально)
- `double_optin` - Использовать двойную подписку (опционально)

**Документация:** https://www.unisender.com/ru/support/api/contacts/subscribe/

### getLists
Получение списка всех списков контактов.

**Документация:** https://www.unisender.com/ru/support/api/contacts/getlists/

### createEmailMessage
Создание email сообщения для массовой рассылки.

**Параметры:**
- `sender_name` - Имя отправителя (обязательно)
- `sender_email` - Email адрес отправителя (обязательно)
- `subject` - Тема письма (обязательно)
- `body` - Тело письма, HTML или текст (обязательно)
- `list_id` - ID списка контактов (опционально)

**Документация:** https://www.unisender.com/ru/support/api/messages/createemailmessage/

### createCampaign
Создание массовой рассылки.

**Параметры:**
- `message_id` - ID сообщения (созданного через createEmailMessage) (обязательно)
- `list_id` - ID списка контактов для рассылки (обязательно)
- `start_time` - Время начала рассылки в формате YYYY-MM-DD HH:MM:SS (опционально)

**Документация:** https://www.unisender.com/ru/support/api/messages/createcampaign/

## Обработка ошибок

Все методы клиента выбрасывают исключения при ошибках API:

```python
try:
    result = client.send_email(...)
except Exception as e:
    print(f"Ошибка: {e}")
```

## Дополнительная информация

- Полная документация API: https://www.unisender.com/ru/support/api/common/bulk-email/
- Получение API ключа: https://www.unisender.com/ru/support/api/common/api-key/
- Лимиты по запросам: https://www.unisender.com/ru/support/api/common/api-limits/
