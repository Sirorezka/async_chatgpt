import openai
from openai.error import RateLimitError, APIError
from aiohttp import ClientSession
import asyncio
from typing import List, Dict
import time


from . import logs_utils

logger = logs_utils.logger


async def create_chat_completion(messages: str, 
                                 model_type: str = "gpt-3.5-turbo",
                                 functions = None):
    """Async call to OpenAI chat completions."""
    if functions is None:
        response = await openai.ChatCompletion.acreate(
                                            messages = messages,
                                            model = model_type, 
                                            )
    else:
        response = await openai.ChatCompletion.acreate(
                                            messages = messages,
                                            model = model_type, 
                                            functions = functions
                                            )
    return response


def _func_task(msg, model_type, functions):
    """Fix issues with arguments passed to different chatGPT models
    
    - Takes care of the problem when you can't pass None instead of functions
    """
    if functions is not None and len(functions)>0:
        return create_chat_completion(msg, model_type, functions)
    else:
        return create_chat_completion(msg, model_type)
        

class ExceptionStats():
    """Stores information about all occured exceptions.

        - Group exceptions by their type.
        - Count exceptions of each type
        - Store one exceptions instances for each exceptions type
    """
    def __init__(self):
        self._data = dict()

    def add_exception(self, ex: Exception):
            ex_type = type(ex)
            if ex_type in self._data:
                self._data[ex_type]['count'] +=1
            else:
                self._data[ex_type] = {}
                self._data[ex_type]['count'] = 1
                self._data[ex_type]['ex'] = ex
    

    def print_stats(self):
        if len(self._data) == 0:
            logger.info(f"No stats on exception collected")

        for err_type in self._data:
            ex_cnt = self._data[err_type]['count']
            exception = self._data[err_type]['ex']
            logger.info(f"Got {ex_cnt} exceptions with type {type(exception)}, msg example: {exception}")


async def multiple_completions(chats: List[Dict[str,str]],
                                model_type: str = "gpt-3.5-turbo",
                                functions: Dict =  [],
                                timeout = 30
                               ):
    """Full async call to OpenAI with rerun of failed tasks.
       
       Parameters:
            chats - List of messages, where messages are the same as in openai.ChatCompletion.create
            model_type - same as in openai.ChatCompletion.create
            functions - same as in openai.ChatCompletion.create
            timeout - retry timeout in seconds, will restart all failed tasks after the timeout.

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

    openai.aiosession.set(ClientSession(loop = nb_loop))
    
    # dictionary with tasks
    # map: task -> task_id
    n_chats = len(chats)
    tasks = {asyncio.ensure_future(_func_task(chats[task_id], model_type, functions), loop=nb_loop): task_id
            for task_id in range(n_chats)}


    pending_ids = [task_id for task, task_id in tasks.items()]

    num_times_called = 0
    cnt_total_failed = 0
    while pending_ids:
        num_times_called += 1
        n_pending = len(pending_ids)
        
        logger.info("{} times called with {} pending tasks: {}".format(num_times_called, n_pending, pending_ids))
        # returns "set" with finished tasks and pending tasks
        finished, pending = await asyncio.wait([task for task in tasks.keys() if not task.done()], 
                                                loop=nb_loop,
                                                return_when=asyncio.ALL_COMPLETED)


        logger.info (f"finished: {len(finished)}")
        logger.info (f"pending: {len(pending)}")

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
                new_task = asyncio.ensure_future(_func_task(chats[task_id], model_type, functions))
                tasks[new_task] = task_id
                pending_ids.append(task_id)

        cnt_total_failed += cnt_failed
        logger.info (f"cnt failed: {cnt_failed}")

        if cnt_failed>0:
            stats_exceptions.print_stats()
            logger.info(f"retrying failed tasks in {timeout} seconds")
            time.sleep(timeout)

    await openai.aiosession.get().close()

    # resorting tasks if needed
    if cnt_total_failed>0:
        # need to resort tasks if some tasks were restarted
        lst_tasks = sorted([task for task in tasks.keys()], key = lambda x: tasks[x])
    else:
        lst_tasks = [task for task in tasks.keys()]

    # extracting tasks results 
    lst_tasks = [task.result() for task in tasks]

    return lst_tasks
