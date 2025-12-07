"""
Модуль для работы с базой данных SQLite
Хранит связи Telegram ID ↔ Bitrix24 User ID
"""
import sqlite3
import logging
import os
from typing import Dict, Optional, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DB_PATH = os.getenv("DATABASE_PATH", "telegram_bitrix_mapping.db")


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Инициализация базы данных - создание таблиц"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица для связей Telegram ID ↔ Bitrix24 User ID
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telegram_bitrix_mapping (
                    telegram_id INTEGER PRIMARY KEY,
                    bitrix_user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, bitrix_user_id)
                )
            """)
            
            # Таблица для связей Telegram username ↔ Bitrix24 User ID
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS username_bitrix_mapping (
                    telegram_username TEXT PRIMARY KEY,
                    bitrix_user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индекс для быстрого поиска по Bitrix User ID
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bitrix_user_id 
                ON telegram_bitrix_mapping(bitrix_user_id)
            """)
            
            logger.info("✅ База данных инициализирована успешно")
            logger.info(f"   Путь к БД: {DB_PATH}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации базы данных: {e}", exc_info=True)
        raise


def save_telegram_mapping(telegram_id: int, bitrix_user_id: int) -> bool:
    """
    Сохранение связи Telegram ID → Bitrix24 User ID
    
    Args:
        telegram_id: Telegram User ID
        bitrix_user_id: Bitrix24 User ID
        
    Returns:
        True если сохранение прошло успешно
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Используем INSERT OR REPLACE для обновления существующей записи
            cursor.execute("""
                INSERT OR REPLACE INTO telegram_bitrix_mapping 
                (telegram_id, bitrix_user_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (telegram_id, bitrix_user_id))
            
            logger.info(f"✅ Связь сохранена в БД: Telegram ID {telegram_id} → Bitrix24 User ID {bitrix_user_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении связи в БД: {e}", exc_info=True)
        return False


def get_bitrix_user_id(telegram_id: int) -> Optional[int]:
    """
    Получение Bitrix24 User ID по Telegram ID
    
    Args:
        telegram_id: Telegram User ID
        
    Returns:
        Bitrix24 User ID или None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bitrix_user_id 
                FROM telegram_bitrix_mapping 
                WHERE telegram_id = ?
            """, (telegram_id,))
            
            row = cursor.fetchone()
            if row:
                return int(row['bitrix_user_id'])
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при получении Bitrix24 User ID из БД: {e}", exc_info=True)
        return None


def get_telegram_id(bitrix_user_id: int) -> Optional[int]:
    """
    Получение Telegram ID по Bitrix24 User ID
    
    Args:
        bitrix_user_id: Bitrix24 User ID
        
    Returns:
        Telegram ID или None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT telegram_id 
                FROM telegram_bitrix_mapping 
                WHERE bitrix_user_id = ?
            """, (bitrix_user_id,))
            
            row = cursor.fetchone()
            if row:
                return int(row['telegram_id'])
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при получении Telegram ID из БД: {e}", exc_info=True)
        return None


def load_all_telegram_mappings() -> Dict[int, int]:
    """
    Загрузка всех связей Telegram ID → Bitrix24 User ID из БД
    
    Returns:
        Словарь {telegram_id: bitrix_user_id}
    """
    mappings = {}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT telegram_id, bitrix_user_id 
                FROM telegram_bitrix_mapping
            """)
            
            rows = cursor.fetchall()
            for row in rows:
                mappings[int(row['telegram_id'])] = int(row['bitrix_user_id'])
            
            if mappings:
                logger.info(f"✅ Загружено {len(mappings)} связей из БД")
            else:
                logger.info("ℹ️ В БД пока нет сохраненных связей")
                
    except Exception as e:
        logger.error(f"Ошибка при загрузке связей из БД: {e}", exc_info=True)
    
    return mappings


def save_username_mapping(telegram_username: str, bitrix_user_id: int) -> bool:
    """
    Сохранение связи Telegram username → Bitrix24 User ID
    
    Args:
        telegram_username: Telegram username (без @)
        bitrix_user_id: Bitrix24 User ID
        
    Returns:
        True если сохранение прошло успешно
    """
    try:
        # Убираем @ если есть
        username = telegram_username.lstrip('@')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO username_bitrix_mapping 
                (telegram_username, bitrix_user_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (username, bitrix_user_id))
            
            logger.info(f"✅ Связь username сохранена в БД: @{username} → Bitrix24 User ID {bitrix_user_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении связи username в БД: {e}", exc_info=True)
        return False


def get_bitrix_user_id_by_username(telegram_username: str) -> Optional[int]:
    """
    Получение Bitrix24 User ID по Telegram username
    
    Args:
        telegram_username: Telegram username (с @ или без)
        
    Returns:
        Bitrix24 User ID или None
    """
    try:
        # Убираем @ если есть
        username = telegram_username.lstrip('@')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bitrix_user_id 
                FROM username_bitrix_mapping 
                WHERE telegram_username = ?
            """, (username,))
            
            row = cursor.fetchone()
            if row:
                return int(row['bitrix_user_id'])
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при получении Bitrix24 User ID по username из БД: {e}", exc_info=True)
        return None


def delete_telegram_mapping(telegram_id: int) -> bool:
    """
    Удаление связи Telegram ID → Bitrix24 User ID
    
    Args:
        telegram_id: Telegram User ID
        
    Returns:
        True если удаление прошло успешно
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM telegram_bitrix_mapping 
                WHERE telegram_id = ?
            """, (telegram_id,))
            
            if cursor.rowcount > 0:
                logger.info(f"✅ Связь удалена из БД: Telegram ID {telegram_id}")
                return True
            else:
                logger.warning(f"⚠️ Связь не найдена в БД: Telegram ID {telegram_id}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении связи из БД: {e}", exc_info=True)
        return False


def get_all_mappings() -> Dict[int, int]:
    """
    Получение всех связей (алиас для load_all_telegram_mappings для совместимости)
    
    Returns:
        Словарь {telegram_id: bitrix_user_id}
    """
    return load_all_telegram_mappings()
