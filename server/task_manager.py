"""
Task Manager для асинхронной обработки запросов с polling.
Хранит задачи в памяти и автоматически очищает старые.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Статусы задачи"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Модель задачи"""
    task_id: str
    status: TaskStatus
    user_id: str
    message: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskManager:
    """Менеджер задач с in-memory хранилищем"""

    def __init__(self, cleanup_interval_seconds: int = 60, task_ttl_minutes: int = 5):
        self.tasks: Dict[str, Task] = {}
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.task_ttl_minutes = task_ttl_minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info(f"TaskManager инициализирован: cleanup_interval={cleanup_interval_seconds}s, ttl={task_ttl_minutes}m")

    def create_task(self, user_id: str, message: str) -> str:
        """Создать новую задачу"""
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            user_id=user_id,
            message=message
        )
        self.tasks[task_id] = task
        logger.info(f"Создана задача {task_id} для пользователя {user_id}")
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Получить задачу по ID"""
        return self.tasks.get(task_id)

    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """Обновить статус задачи"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            self.tasks[task_id].updated_at = datetime.now()
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                self.tasks[task_id].completed_at = datetime.now()
            logger.info(f"Задача {task_id}: статус обновлен на {status}")

    def set_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Установить результат задачи"""
        if task_id in self.tasks:
            self.tasks[task_id].result = result
            self.tasks[task_id].updated_at = datetime.now()
            logger.info(f"Задача {task_id}: результат установлен")

    def set_error(self, task_id: str, error: str) -> None:
        """Установить ошибку задачи"""
        if task_id in self.tasks:
            self.tasks[task_id].error = error
            self.tasks[task_id].updated_at = datetime.now()
            logger.error(f"Задача {task_id}: ошибка - {error}")

    async def _cleanup_old_tasks(self) -> None:
        """Фоновая задача очистки старых задач"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)

                completed_cutoff = datetime.now() - timedelta(minutes=self.task_ttl_minutes)
                pending_cutoff = datetime.now() - timedelta(minutes=15)  # 15 минут для pending
                tasks_to_remove = []

                for task_id, task in self.tasks.items():
                    # Удаляем завершенные/ошибочные задачи старше 5 минут
                    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                        if task.completed_at and task.completed_at < completed_cutoff:
                            tasks_to_remove.append(task_id)
                    # Удаляем задачи в pending более 15 минут (точно зависли)
                    elif task.status == TaskStatus.PENDING and task.created_at < pending_cutoff:
                        logger.warning(f"Задача {task_id} зависла в pending, удаляем")
                        tasks_to_remove.append(task_id)
                    # Processing задачи НЕ удаляем - они могут работать долго (6-7 минут)

                for task_id in tasks_to_remove:
                    del self.tasks[task_id]

                if tasks_to_remove:
                    logger.info(f"Очищено {len(tasks_to_remove)} старых задач. Осталось: {len(self.tasks)}")

            except Exception as e:
                logger.error(f"Ошибка при очистке задач: {e}")

    def start_cleanup(self) -> None:
        """Запустить фоновую очистку"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_tasks())
            logger.info("Фоновая очистка задач запущена")

    async def stop_cleanup(self) -> None:
        """Остановить фоновую очистку"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Фоновая очистка задач остановлена")

    def get_stats(self) -> Dict[str, int]:
        """Получить статистику задач"""
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        for task in self.tasks.values():
            stats[task.status.value] += 1
        return stats


# Глобальный экземпляр
task_manager = TaskManager(cleanup_interval_seconds=60, task_ttl_minutes=5)
