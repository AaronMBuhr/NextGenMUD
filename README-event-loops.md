# Event Loop Architecture & the "bound to a different event loop" Bug

## Architecture: Two Event Loops

NextGenMUD runs **two independent asyncio event loops** in separate threads:

### 1. Channels / ASGI Event Loop (Daphne)

- **Created by:** the ASGI server (Daphne) at process start
- **Thread:** the main thread
- **Responsibilities:**
  - WebSocket accept / disconnect lifecycle (`MyWebsocketConsumer`)
  - Login state machine (`_handle_login_input`, `_complete_login`)
  - Receiving player input from the browser and pushing it onto `input_queue`

### 2. Game Main Loop (`MainProcess`)

- **Created by:** `MainProcess.run_main_game_loop()` — calls `asyncio.new_event_loop()` explicitly
- **Thread:** a daemon thread started from the world-loader thread (`apps.py` → `loader_worker` → `MainProcess.start_main_process()`)
- **Responsibilities:**
  - Processing player input from `input_queue` (command handling)
  - Game ticks (combat rounds, regeneration, scheduled events)
  - Timer-tick triggers, NPC AI, aggro checks
  - Sending game output back to players via `Connection.send()` → `consumer.send()`

### Data Flow Across the Two Loops

```
Browser  ──WebSocket──►  Channels loop (Daphne)
                              │
                              │  consumer.receive() appends to input_queue
                              ▼
                         input_queue (collections.deque — thread-safe)
                              │
                              │  Game loop drains input_queue each tick
                              ▼
                         Game loop (MainProcess thread)
                              │
                              │  Game logic calls Connection.send()
                              │  which calls consumer.send()
                              ▼
Browser  ◄──WebSocket──  Channels loop (Daphne)
```

The critical crossing point is `Connection.send()`. The game loop thread calls
`await consumer.send(...)` on a Django Channels consumer that was originally
created and is managed by the Channels event loop. This works because
`consumer.send()` ultimately writes bytes to the socket, and the underlying
WebSocket protocol object is not strictly loop-bound. However, any **asyncio
synchronisation primitives** (Lock, Event, Semaphore, etc.) that are created in
one loop cannot be acquired in the other.

---

## The Bug

### Symptom

```
RuntimeError: <asyncio.locks.Lock object at 0x...> is bound to a different event loop
```

Traceback passes through:

```
_complete_login  (Channels loop)
  → complete_login
    → _load_existing_character
      → arrive_room
        → do_aggro
          → c.echo()           ← "c" is an already-connected player
            → Connection.send()
              → async with self.consumer_._send_lock   ← BOOM
```

### Root Cause

`Connection.send()` lazily creates an `asyncio.Lock` on the consumer to
serialise writes (a workaround for overlapping-write issues on the Windows
Proactor event loop):

```python
if not hasattr(self.consumer_, "_send_lock"):
    self.consumer_._send_lock = asyncio.Lock()
async with self.consumer_._send_lock:
    ...
```

In Python 3.10+, `asyncio.Lock` binds to the **running** event loop at
creation time. If the game loop thread is the first to call `Connection.send()`
for a given consumer (which is common — the game loop sends combat text, room
echoes, status updates, etc.), the lock gets bound to the **game loop**. Later,
when the **Channels loop** also needs to send through the same consumer (e.g.
during a new player's login flow that triggers `do_aggro` against an
already-connected player), it tries to acquire a lock bound to a different
loop.

### Why It Only Triggers Sometimes

- It requires a **cross-loop call path**: the Channels loop must call
  `Connection.send()` on a consumer whose lock was previously created in the
  game loop. This only happens when the Channels-side login flow reaches code
  that sends messages to *other* already-connected players (e.g. `do_aggro`,
  room echoes on arrival).
- If the player is the first to connect (no one else in the room), the code
  path is never hit.

---

## Fix Options

### Option A: Catch-and-Recreate (current fix — recommended)

Wrap the lock acquisition in a `try/except RuntimeError` and recreate the lock
for the current event loop on mismatch:

```python
# communication.py — Connection.send()
if not hasattr(self.consumer_, "_send_lock"):
    self.consumer_._send_lock = asyncio.Lock()
try:
    async with self.consumer_._send_lock:
        await _do_send()
except RuntimeError as exc:
    if "different event loop" in str(exc):
        self.consumer_._send_lock = asyncio.Lock()
        async with self.consumer_._send_lock:
            await _do_send()
    else:
        raise
```

**Pros:** Minimal change, no architectural rework, handles any loop mismatch
automatically.

**Cons:** Each loop effectively gets its own lock instance, so writes from the
game loop and writes from the Channels loop are not serialised *against each
other*. In practice this is acceptable because concurrent cross-loop sends to
the same consumer are rare (the Channels loop almost never sends game text
directly).

### Option B: Remove the Lock Entirely

```python
async def send(self, text_type, text_data: str):
    ...
    await self.consumer_.send(text_data=payload)
    await asyncio.sleep(0)
```

**Pros:** Simplest possible code, no lock management at all.

**Cons:** The lock was originally added to work around overlapping-write
corruption on the Windows Proactor loop. Removing it may reintroduce that
issue. However, `MainProcess.run_main_game_loop` already sets
`WindowsSelectorEventLoopPolicy` (line 70–71 of `main_process.py`) which
avoids the Proactor loop entirely on the game-loop side. If the Channels/ASGI
server also avoids Proactor (Daphne uses Twisted, which does), the lock may be
unnecessary.

### Option C: Route All Sends Through the Channels Loop

Instead of calling `consumer.send()` directly from the game loop, use Django
Channels' `channel_layer` to post a message that the Channels loop picks up:

```python
# In Connection.send():
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()
await channel_layer.send(self.consumer_.channel_name, {
    "type": "game.send",
    "text_type": text_type,
    "text": text_data,
})

# In MyWebsocketConsumer:
async def game_send(self, event):
    await self.send(text_data=json.dumps({
        "text_type": event["text_type"],
        "text": event["text"],
    }))
```

**Pros:** Architecturally correct — all WebSocket writes happen in the loop
that owns the socket. Eliminates the cross-loop issue entirely. Also makes
future scaling (e.g. multi-process with Redis channel layer) possible.

**Cons:** Requires a channel layer backend (in-memory is fine for single-process).
Adds latency (message goes through the channel layer instead of a direct call).
Significant refactor — every `Connection.send()` call becomes an inter-loop
message.

### Option D: Unify Into a Single Event Loop

Run the game loop as a long-lived `asyncio.Task` inside the Channels event
loop instead of a separate thread:

```python
# In apps.py ready(), after world loads:
import asyncio
loop = asyncio.get_event_loop()
loop.create_task(MainProcess.main_game_loop())
```

**Pros:** One loop, zero cross-loop issues, simpler mental model.

**Cons:** Major architectural change. The game loop's `asyncio.sleep()` and
CPU-bound tick work share the event loop with WebSocket I/O, which could
introduce latency spikes. Needs careful profiling. Also, Daphne's event loop
may not be easily accessible from `AppConfig.ready()`.

---

## Recommendation

**Use Option A (catch-and-recreate)** as the immediate fix. It is safe,
minimal, and already deployed. The cross-loop lock-splitting trade-off is
acceptable given current traffic patterns.

If the project later needs multi-process scaling or you want to clean up the
architecture, **Option C (channel layer routing)** is the proper long-term
solution. It keeps each event loop owning its own I/O and makes the
architecture compatible with Redis-backed channel layers for horizontal
scaling.
