# NextGenMUD/asgi.py

import os
import signal
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import NextGenMUDApp.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NextGenMUD.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

inner_application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            NextGenMUDApp.routing.websocket_urlpatterns
        )
    ),
})


async def application(scope, receive, send):
    """
    ASGI application wrapper that handles lifespan events.
    
    This wrapper serves two purposes:
    1. Registers a SIGINT handler after Uvicorn's, ensuring our shutdown flags
       are set BEFORE Uvicorn closes WebSocket connections on Ctrl+C.
    2. Handles graceful shutdown with proper cleanup of external resources.
    """
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                # Startup: Register our signal handler after Uvicorn's
                from NextGenMUDApp.main_process import MainProcess
                
                original_handler = signal.getsignal(signal.SIGINT)
                
                def shutdown_handler(signum, frame):
                    # Set our shutdown flags FIRST
                    MainProcess.shutdown()
                    # Then call original handler (Uvicorn's) to continue shutdown
                    if callable(original_handler):
                        original_handler(signum, frame)
                
                signal.signal(signal.SIGINT, shutdown_handler)
                
                await send({"type": "lifespan.startup.complete"})
            
            elif message["type"] == "lifespan.shutdown":
                import asyncio
                import concurrent.futures
                import gc
                
                from NextGenMUDApp.main_process import MainProcess
                MainProcess.shutdown()
                
                # Attempt graceful shutdown of asyncio's default executor
                try:
                    loop = asyncio.get_running_loop()
                    await loop.shutdown_default_executor()
                except Exception:
                    pass
                
                # Attempt to shutdown any other ThreadPoolExecutors (e.g., from Gemini/httpx)
                for obj in gc.get_objects():
                    if isinstance(obj, concurrent.futures.ThreadPoolExecutor):
                        try:
                            obj.shutdown(wait=False, cancel_futures=True)
                        except Exception:
                            pass
                
                await send({"type": "lifespan.shutdown.complete"})
                
                # FORCED EXIT REQUIRED - Here's why:
                #
                # The Google Gemini API client (google-genai) uses httpx internally, which
                # creates a ThreadPoolExecutor with non-daemon worker threads. These threads
                # are used for HTTP connection pooling and async I/O operations.
                #
                # Problem: Python's normal exit process waits for ALL non-daemon threads to
                # finish before terminating. The httpx ThreadPoolExecutor threads sit idle
                # waiting for work that will never come, causing the process to hang
                # indefinitely after "Finished server process" is printed.
                #
                # We tried several approaches that DON'T work:
                # - shutdown_default_executor(): Only affects asyncio's executor, not httpx's
                # - ThreadPoolExecutor.shutdown(wait=False): Stops accepting new work but
                #   doesn't terminate threads already waiting on the internal queue
                # - Closing the Gemini client: The httpx client doesn't expose a clean way
                #   to terminate its thread pool workers
                #
                # The solution: os._exit(0) bypasses Python's normal cleanup and immediately
                # terminates the process. This is safe here because:
                # 1. All player data has already been saved (in handle_disconnect)
                # 2. MainProcess.shutdown() has signaled the game loop to stop
                # 3. We've sent lifespan.shutdown.complete to Uvicorn
                # 4. All application-level cleanup is complete
                #
                # Note: os._exit() skips atexit handlers and finally blocks, but since we've
                # done all necessary cleanup above, this is acceptable.
                os._exit(0)
    else:
        # Delegate all other requests to the inner application
        await inner_application(scope, receive, send)
