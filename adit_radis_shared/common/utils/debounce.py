import threading
from functools import wraps


def debounce(wait_time=1):
    """Decorator that will debounce a function.

    #
    Function is called after wait_time in seconds.  If it is called multiple times,
    it will wait for the last call to be debounced and run only this one.
    """

    def decorator(func):
        timer: threading.Timer | None = None

        @wraps(func)
        def debounced(*args, **kwargs):
            nonlocal timer

            def call_function():
                nonlocal timer
                timer = None
                return func(*args, **kwargs)

            if timer is not None:
                timer.cancel()

            timer = threading.Timer(wait_time, call_function)
            timer.start()

        timer = None
        return debounced

    return decorator
