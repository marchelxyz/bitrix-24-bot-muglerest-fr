"""
Модуль для отслеживания задач в Bitrix24 и отправки уведомлений в Telegram
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from bitrix24_client import Bitrix24Client

try:
    import database
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class TaskNotificationService:
    """Сервис для отслеживания задач и отправки уведомлений"""
    
    def __init__(self, bitrix_client: Bitrix24Client, telegram_bot, telegram_group_id: int):
        """
        Инициализация сервиса уведомлений
        
        Args:
            bitrix_client: Клиент для работы с Bitrix24 API
            telegram_bot: Экземпляр Telegram бота для отправки сообщений
            telegram_group_id: ID Telegram супергруппы для отправки уведомлений
        """
        self.bitrix_client = bitrix_client
        self.telegram_bot = telegram_bot
        self.telegram_group_id = telegram_group_id
        
        # Настройки уведомлений из переменных окружения
        self.check_interval_minutes = int(os.getenv("TASK_NOTIFICATION_CHECK_INTERVAL", "60"))  # По умолчанию каждый час
        self.deadline_warning_hours = int(os.getenv("TASK_DEADLINE_WARNING_HOURS", "24"))  # За сколько часов предупреждать
        self.enable_overdue_notifications = os.getenv("ENABLE_OVERDUE_NOTIFICATIONS", "true").lower() == "true"
        self.enable_deadline_warnings = os.getenv("ENABLE_DEADLINE_WARNINGS", "true").lower() == "true"
        self.enable_comment_notifications = os.getenv("ENABLE_COMMENT_NOTIFICATIONS", "true").lower() == "true"
        
        # Используем БД для отслеживания отправленных уведомлений
        self.use_database = DATABASE_AVAILABLE
        # Fallback: множество для отслеживания в памяти, если БД недоступна
        self.sent_notifications: Set[str] = set()
    
    def _get_notification_key(self, task_id: int, notification_type: str, extra: str = "") -> str:
        """
        Генерация уникального ключа для уведомления
        
        Args:
            task_id: ID задачи
            notification_type: Тип уведомления (overdue, deadline_warning, comment)
            extra: Дополнительная информация (например, ID комментария)
            
        Returns:
            Уникальный ключ уведомления
        """
        return f"{task_id}_{notification_type}_{extra}"
    
    def _was_notification_sent(self, notification_key: str) -> bool:
        """Проверка, было ли уже отправлено уведомление"""
        if self.use_database:
            return database.was_notification_sent(notification_key)
        return notification_key in self.sent_notifications
    
    def _mark_notification_sent(self, notification_key: str, task_id: int, notification_type: str, extra_data: str = None):
        """Отметить уведомление как отправленное"""
        if self.use_database:
            database.mark_notification_sent(notification_key, task_id, notification_type, extra_data)
        else:
            self.sent_notifications.add(notification_key)
    
    async def _send_notification(self, message: str, user_telegram_id: Optional[int] = None):
        """
        Отправка уведомления в Telegram супергруппу
        
        Args:
            message: Текст сообщения
            user_telegram_id: Telegram ID пользователя для упоминания (опционально)
        """
        try:
            # Формируем текст с упоминанием пользователя, если указан
            # В Telegram супергруппах упоминание делается через user_id
            if user_telegram_id:
                # Пробуем получить информацию о пользователе из чата для упоминания
                try:
                    # Получаем информацию о пользователе из чата
                    chat_member = await self.telegram_bot.get_chat_member(
                        chat_id=self.telegram_group_id,
                        user_id=user_telegram_id
                    )
                    user_name = chat_member.user.first_name or chat_member.user.username or f"Пользователь {user_telegram_id}"
                    # Используем HTML формат для упоминания: <a href="tg://user?id=USER_ID">имя</a>
                    full_message = f"<a href='tg://user?id={user_telegram_id}'>{user_name}</a>, {message}"
                except Exception as member_error:
                    # Если не удалось получить информацию о пользователе, используем простой формат
                    logger.debug(f"Не удалось получить информацию о пользователе {user_telegram_id}: {member_error}")
                    # Используем формат с user_id для упоминания
                    full_message = f"<a href='tg://user?id={user_telegram_id}'>Пользователь</a>, {message}"
            else:
                full_message = message
            
            await self.telegram_bot.send_message(
                chat_id=self.telegram_group_id,
                text=full_message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            logger.info(f"✅ Уведомление отправлено в группу {self.telegram_group_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке уведомления: {e}", exc_info=True)
    
    async def check_overdue_tasks(self):
        """Проверка просроченных задач"""
        if not self.enable_overdue_notifications:
            return
        
        try:
            logger.info("🔍 Проверка просроченных задач...")
            
            # Получаем все задачи с просроченным дедлайном
            # Используем фильтр по DEADLINE < текущая дата и STATUS != завершена
            now = datetime.now()
            # Bitrix24 использует формат фильтров через операторы
            # Для просроченных задач: DEADLINE < текущая дата и STATUS не равен 5 (завершена)
            tasks = self.bitrix_client.get_tasks(
                filter_params={
                    "<DEADLINE": now.strftime('%Y-%m-%d %H:%M:%S'),
                    "!STATUS": "5"  # Исключаем завершенные задачи (статус 5 = завершена)
                }
            )
            
            for task in tasks:
                task_id = task.get("id")
                deadline_str = task.get("deadline")
                responsible_id = task.get("responsibleId")
                
                if not task_id or not deadline_str:
                    continue
                
                # Проверяем, не отправляли ли уже уведомление
                notification_key = self._get_notification_key(task_id, "overdue")
                if self._was_notification_sent(notification_key):
                    continue
                
                # Получаем Telegram ID ответственного
                telegram_id = None
                if responsible_id:
                    telegram_id = self.bitrix_client.get_user_telegram_id(int(responsible_id))
                
                # Формируем ссылку на задачу
                task_url = self.bitrix_client.get_task_url(int(task_id), responsible_id)
                
                # Формируем сообщение
                task_title = task.get("title", "Без названия")
                message = f"срок выполнения задачи <a href='{task_url}'>«{task_title}»</a> просрочен"
                
                # Отправляем уведомление
                await self._send_notification(message, telegram_id)
                self._mark_notification_sent(notification_key, int(task_id), "overdue")
                
                logger.info(f"✅ Отправлено уведомление о просроченной задаче {task_id}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке просроченных задач: {e}", exc_info=True)
    
    async def check_deadline_warnings(self):
        """Проверка задач с приближающимся дедлайном"""
        if not self.enable_deadline_warnings:
            return
        
        try:
            logger.info(f"🔍 Проверка задач с дедлайном через {self.deadline_warning_hours} часов...")
            
            # Вычисляем время предупреждения
            warning_time = datetime.now() + timedelta(hours=self.deadline_warning_hours)
            now = datetime.now()
            
            # Получаем задачи с дедлайном в ближайшие N часов
            # Bitrix24 использует операторы >= и <= для фильтров
            tasks = self.bitrix_client.get_tasks(
                filter_params={
                    ">=DEADLINE": now.strftime('%Y-%m-%d %H:%M:%S'),
                    "<=DEADLINE": warning_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "!STATUS": "5"  # Исключаем завершенные задачи
                }
            )
            
            for task in tasks:
                task_id = task.get("id")
                deadline_str = task.get("deadline")
                responsible_id = task.get("responsibleId")
                
                if not task_id or not deadline_str:
                    continue
                
                # Проверяем, не отправляли ли уже уведомление
                notification_key = self._get_notification_key(task_id, "deadline_warning")
                if self._was_notification_sent(notification_key):
                    continue
                
                # Получаем Telegram ID ответственного
                telegram_id = None
                if responsible_id:
                    telegram_id = self.bitrix_client.get_user_telegram_id(int(responsible_id))
                
                # Формируем ссылку на задачу
                task_url = self.bitrix_client.get_task_url(int(task_id), responsible_id)
                
                # Формируем сообщение
                task_title = task.get("title", "Без названия")
                # Парсим дату дедлайна (Bitrix24 может возвращать в разных форматах)
                try:
                    # Пробуем разные форматы даты
                    if 'T' in deadline_str or 'Z' in deadline_str:
                        # ISO формат с временной зоной
                        deadline_dt = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
                        # Убираем временную зону для вычисления разницы
                        if deadline_dt.tzinfo:
                            deadline_dt = deadline_dt.replace(tzinfo=None)
                    else:
                        # Простой формат YYYY-MM-DD HH:MI:SS
                        deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M:%S')
                    
                    now = datetime.now()
                    hours_left = int((deadline_dt - now).total_seconds() / 3600)
                    if hours_left < 0:
                        hours_left = 0
                except Exception as date_error:
                    logger.warning(f"Ошибка при парсинге даты дедлайна {deadline_str}: {date_error}")
                    hours_left = self.deadline_warning_hours  # Используем значение по умолчанию
                
                message = f"срок выполнения задачи <a href='{task_url}'>«{task_title}»</a> истекает через {hours_left} часов"
                
                # Отправляем уведомление
                await self._send_notification(message, telegram_id)
                self._mark_notification_sent(notification_key, int(task_id), "deadline_warning")
                
                logger.info(f"✅ Отправлено предупреждение о дедлайне задачи {task_id}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке предупреждений о дедлайне: {e}", exc_info=True)
    
    async def check_task_comments(self, last_check_time: Optional[datetime] = None):
        """
        Проверка новых комментариев в задачах
        
        ВАЖНО: Метод tasks.task.commentitem.getlist не существует в Bitrix24 API.
        Для отслеживания изменений задач (комментарии, статусы) необходимо использовать
        исходящий вебхук Bitrix24 (Outgoing Webhook).
        
        События для настройки в исходящем вебхуке:
        - ONTASKADD - Создание задачи
        - ONTASKUPDATE - Обновление задачи (включая изменение статуса)
        - ONTASKDELETE - Удаление задачи
        - ONTASKCOMMENTADD - Добавление комментария к задаче
        - ONTASKCOMMENTUPDATE - Обновление комментария к задаче
        - ONTASKCOMMENTDELETE - Удаление комментария к задаче
        
        Args:
            last_check_time: Время последней проверки (опционально)
        """
        if not self.enable_comment_notifications:
            return
        
        # Отключаем проверку комментариев через API, так как метод не существует
        logger.warning("⚠️ Проверка комментариев через API отключена")
        logger.info("💡 Для отслеживания изменений задач (комментарии, статусы) используйте исходящий вебхук Bitrix24")
        logger.info("   Настройка: Bitrix24 → Настройки → Разработчикам → Исходящий вебхук")
        logger.info("   События задач: ONTASKADD, ONTASKUPDATE, ONTASKDELETE")
        logger.info("   События комментариев: ONTASKCOMMENTADD, ONTASKCOMMENTUPDATE, ONTASKCOMMENTDELETE")
        return
    
    async def run_periodic_check(self):
        """Запуск периодической проверки задач"""
        logger.info("🔄 Запуск периодической проверки задач...")
        
        # Проверяем просроченные задачи
        await self.check_overdue_tasks()
        
        # Проверяем предупреждения о дедлайне
        await self.check_deadline_warnings()
        
        # Проверка комментариев отключена - метод tasks.task.commentitem.getlist не существует
        # Для отслеживания изменений задач используйте исходящий вебхук Bitrix24
        # await self.check_task_comments()
        
        logger.info("✅ Периодическая проверка задач завершена")
