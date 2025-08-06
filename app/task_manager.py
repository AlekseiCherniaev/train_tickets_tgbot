import asyncio
from collections import defaultdict


class TaskManager:
    def __init__(self) -> None:
        self.active_tasks: dict[int, list[asyncio.Task]] = defaultdict(  # type: ignore
            list
        )  # {chat_id: [tasks]}

    def add_task(self, chat_id: int, task: asyncio.Task) -> None:  # type: ignore
        self.active_tasks[chat_id].append(task)

    async def cancel_all_tasks(self) -> None:
        for tasks in self.active_tasks.values():
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    def get_active_users(self) -> set[int]:
        return {
            chat_id
            for chat_id, tasks in self.active_tasks.items()
            if any(not t.done() for t in tasks)
        }


task_manager = TaskManager()
