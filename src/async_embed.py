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


def is_loog_arg(func):
    """Checks if you need to pass 'loop' argument to a function."""
    sign = str(inspect.signature(func))
    if ", loop=" in sign:
        return True

    return False


async def create_embeddings(input_txt: str, model_type: str = "text-embedding-ada-002"):
    response = await openai.Embedding.acreate(
        input=input_txt,
        model=model_type,
    )
    return response


def _func_task(input_txt: str, model_type: str):
    """Fix issues with arguments passed to different chatGPT models."""
    return create_embeddings(input_txt, model_type)


async def multiple_embeddings(
    chats: List[str], model_type: str = "text-embedding-ada-002", timeout=30
):
    """Full async call to OpenAI with rerun of failed tasks.

    Parameters:
         chats - List of inputs, where input is the same as in openai.Embedding.create
         model_type - same as in openai.Embedding.create
         functions - same as in openai.Embedding.create
         timeout - retry timeout in seconds, will restart all failed tasks after the timeout.

     Parameters example:

     chats = [input_txt1, input_txt2, input_txt3, ...]
     model_type = "text-embedding-ada-002"

    """

    # If running from notebook it is advised to reuse existing jupyter event-loop
    try:
        nb_loop = asyncio.get_event_loop()
    except:
        nb_loop = None

    openai.aiosession.set(ClientSession(loop=nb_loop))

    # dictionary with tasks
    # map: task -> task_id
    n_chats = len(chats)
    tasks = {
        asyncio.ensure_future(
            _func_task(chats[task_id], model_type), loop=nb_loop
        ): task_id
        for task_id in range(n_chats)
    }

    pending_ids = [task_id for _, task_id in tasks.items()]

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
            )
        else:
            finished, pending = await asyncio.wait(
                [task for task in tasks.keys() if not task.done()],
                return_when=asyncio.ALL_COMPLETED,
            )

        logger.info(f"finished: {len(finished)}")
        logger.info(f"pending: {len(pending)}")

        pending_ids = []
        cnt_failed = 0
        stats_exceptions = ExceptionStats()
        for task in finished:
            if task.exception():
                cnt_failed += 1

                # saving tasks exceptions for statistincst
                stats_exceptions.add_exception(task.exception())

                # replacing failed task with new one
                task_id = tasks.pop(task)
                new_task = asyncio.ensure_future(_func_task(chats[task_id], model_type))
                tasks[new_task] = task_id
                pending_ids.append(task_id)

        cnt_total_failed += cnt_failed
        logger.info(f"cnt failed: {cnt_failed}")

        if cnt_failed > 0:
            stats_exceptions.print_stats()
            logger.info(f"retrying failed tasks in {timeout} seconds")
            time.sleep(timeout)

    await openai.aiosession.get().close()

    # resorting tasks if needed
    if cnt_total_failed > 0:
        # need to resort tasks if some tasks were restarted
        lst_tasks = sorted([task for task in tasks.keys()], key=lambda x: tasks[x])
    else:
        lst_tasks = [task for task in tasks.keys()]

    # extracting tasks results
    lst_tasks = [task.result() for task in tasks]

    return lst_tasks
