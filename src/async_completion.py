import openai
from openai.error import RateLimitError, APIError
from aiohttp import ClientSession
import asyncio
from typing import List, Dict
import time
import inspect

from . import logs_utils

logger = logs_utils.logger
ExceptionStats = logs_utils.ExceptionStats


async def create_chat_completion(
    messages: List[Dict[str, str]], model_type: str = "gpt-3.5-turbo", **kwgs
):
    """Async call to OpenAI chat completions."""
    response = await openai.ChatCompletion.acreate(
        messages=messages, model=model_type, **kwgs
    )
    return response


def _func_task(
    msg: List[Dict[str, str]],
    model_type: str = "gpt-3.5-turbo",
    functions=None,
    temperature=None,
):
    """Fix issues with arguments passed to different chatGPT models

    - Takes care of the problem when you can't pass None instead of functions
    """

    kwgs = {
        "messages": msg,
        "model_type": model_type,
    }
    if functions is not None and len(functions) > 0:
        kwgs["functions"] = functions

    if temperature is not None and temperature >= 0:
        kwgs["temperature"] = temperature

    return create_chat_completion(**kwgs)


def is_loog_arg(func):
    """Checks if you need to pass 'loop' argument to a function."""
    sign = str(inspect.signature(func))
    if ", loop=" in sign:
        return True

    return False


async def multiple_completions(
    chats: List[Dict[str, str]],
    model_type: str = "gpt-3.5-turbo",
    functions: Dict = [],
    timeout=30,
    timeout_async=50,
    temperature=None,
    use_logs=True,
):
    """Full async call to OpenAI with rerun of failed tasks.

    Parameters:
         chats - List of messages, where messages are the same as in openai.ChatCompletion.create
         model_type - same as in openai.ChatCompletion.create
         functions - same as in openai.ChatCompletion.create
         timeout_async - how long to wait for a response from API;
         timeout - how long to wait before restarting failed and long pending tasks

     Parameters example:

     messages1 = [{'role': 'system',
                 'content': 'You are a proffessional psychiatrist. Psychiatrists assess user mental and physical symptoms'},
                 {'role': 'user',
                 'content': 'Hello World'}]
     chats = [messages1, messages2, messages3, ...]
      model_type = "gpt-3.5-turbo"

    """

    # If running from notebook it is advised to reuse existing jupyter event-loop
    try:
        nb_loop = asyncio.get_event_loop()
    except:
        nb_loop = None

    if not use_logs:
        saved_handlers = logger.handlers
        logger.handlers = []

    openai.aiosession.set(ClientSession(loop=nb_loop))

    # dictionary with tasks
    # map: task -> task_id
    n_chats = len(chats)
    tasks = {
        asyncio.ensure_future(
            _func_task(chats[task_id], model_type, functions, temperature), loop=nb_loop
        ): task_id
        for task_id in range(n_chats)
    }

    pending_ids = [task_id for task, task_id in tasks.items()]

    num_times_called = 0
    cnt_total_failed = 0
    while pending_ids:
        num_times_called += 1
        n_pending = len(pending_ids)

        logger.info(
            "{} times called with {} pending tasks: {}".format(
                num_times_called, n_pending, pending_ids
            )
        )

        # different versions of asyncio.wait have different arguments
        if is_loog_arg(asyncio.wait):
            # returns "set" with finished tasks and pending tasks
            finished, pending = await asyncio.wait(
                [task for task in tasks.keys() if not task.done()],
                loop=nb_loop,
                return_when=asyncio.ALL_COMPLETED,
                timeout=timeout_async,
            )
        else:
            finished, pending = await asyncio.wait(
                [task for task in tasks.keys() if not task.done()],
                return_when=asyncio.ALL_COMPLETED,
                timeout=timeout_async,
            )

        logger.info(f"finished: {len(finished)}")
        logger.info(f"pending: {len(pending)}")

        pending_ids = []
        cnt_canceled = 0
        # Add pending tasks to canceled
        if len(pending) > 0:
            for task in pending:
                cnt_canceled += 1
                task.cancel(msg="canceled by timeout")
                task_id = tasks.pop(task)
                pending_ids.append(task_id)

        cnt_failed = 0
        stats_exceptions = ExceptionStats()
        for task in finished:
            if task.exception():
                cnt_failed += 1
                # saving tasks exceptions for statistic
                stats_exceptions.add_exception(task.exception())
                task_id = tasks.pop(task)
                pending_ids.append(task_id)

        cnt_total_failed += cnt_failed
        logger.info(f"cnt canceled (by timeout): {cnt_canceled}")
        logger.info(f"cnt failed: {cnt_failed}")

        if len(pending_ids) > 0:
            stats_exceptions.print_stats()
            logger.info(f"retrying failed tasks in {timeout} seconds")
            time.sleep(timeout)

        for task_id in pending_ids:
            # replacing failed task with new one
            new_task = asyncio.ensure_future(
                _func_task(chats[task_id], model_type, functions)
            )
            tasks[new_task] = task_id

    await openai.aiosession.get().close()

    # resorting tasks if needed
    if cnt_total_failed > 0:
        # need to resort tasks if some tasks were restarted
        lst_tasks = sorted([task for task in tasks.keys()], key=lambda x: tasks[x])
    else:
        lst_tasks = [task for task in tasks.keys()]

    # extracting tasks results
    lst_tasks = [task.result() for task in tasks]

    if not use_logs:
        logger.handlers = saved_handlers

    return lst_tasks
