"""SocketIO server for handling real-time communication between clients."""

import asyncio
import time

import socketio
from loguru import logger

from open_webui.env import (
    ENABLE_WEBSOCKET_SUPPORT,
    WEBSOCKET_MANAGER,
    env,
)
from open_webui.models.channels import Channels
from open_webui.models.chats import Chats
from open_webui.models.users import UserNameResponse, Users
from open_webui.socket.utils import RedisDict, RedisLock
from open_webui.utils.auth import decode_token

if WEBSOCKET_MANAGER == "redis":
    client_manager = socketio.AsyncRedisManager(env.REDIS_URL)
else:
    client_manager = None

sio = socketio.AsyncServer(
    client_manager=client_manager,
    cors_allowed_origins=[],
    async_mode="asgi",
    transports=(["websocket"] if ENABLE_WEBSOCKET_SUPPORT else ["polling"]),
    allow_upgrades=ENABLE_WEBSOCKET_SUPPORT,
    always_connect=True,
)
# Timeout duration in seconds
TIMEOUT_DURATION = 3

# Dictionary to maintain the user pool

if WEBSOCKET_MANAGER == "redis":
    logger.debug("Using Redis to manage websockets.")
    SESSION_POOL = RedisDict("open-webui:session_pool", redis_url=env.REDIS_URL)
    USER_POOL = RedisDict("open-webui:user_pool", redis_url=env.REDIS_URL)
    USAGE_POOL = RedisDict("open-webui:usage_pool", redis_url=env.REDIS_URL)

    clean_up_lock = RedisLock(
        redis_url=env.REDIS_URL,
        lock_name="usage_cleanup_lock",
        timeout_secs=TIMEOUT_DURATION * 2,
    )
    aquire_func = clean_up_lock.aquire_lock
    renew_func = clean_up_lock.renew_lock
    release_func = clean_up_lock.release_lock
else:
    SESSION_POOL = {}
    USER_POOL = {}
    USAGE_POOL = {}
    aquire_func = release_func = renew_func = lambda: True


async def periodic_usage_pool_cleanup():
    """Periodically clean up the usage pool."""
    if not aquire_func():
        logger.debug("Usage pool cleanup lock already exists. Not running it.")
        return
    logger.debug("Running periodic_usage_pool_cleanup")
    try:
        while True:
            if not renew_func():
                logger.error(
                    "Unable to renew cleanup lock. Exiting usage pool cleanup."
                )
                raise Exception("Unable to renew usage pool cleanup lock.")

            now = int(time.time())
            send_usage = False
            for model_id, connections in list(USAGE_POOL.items()):
                # Creating a list of sids to remove if they have timed out
                expired_sids = [
                    sid
                    for sid, details in connections.items()
                    if now - details["updated_at"] > TIMEOUT_DURATION
                ]

                for sid in expired_sids:
                    del connections[sid]

                if not connections:
                    logger.debug(f"Cleaning up model {model_id} from usage pool")
                    del USAGE_POOL[model_id]
                else:
                    USAGE_POOL[model_id] = connections

                send_usage = True

            if send_usage:
                # Emit updated usage information after cleaning
                await sio.emit("usage", {"models": get_models_in_use()})

            await asyncio.sleep(TIMEOUT_DURATION)
    finally:
        release_func()


app = socketio.ASGIApp(
    sio,
    socketio_path="/ws/socket.io",
)


def get_models_in_use():
    """Get the list of models that are currently in use."""
    # List models that are currently in use
    return list(USAGE_POOL.keys())  # type: ignore


@sio.on("usage")  # type: ignore
async def usage(sid, data):
    """Usage event."""
    model_id = data["model"]
    # Record the timestamp for the last update
    current_time = int(time.time())

    # Store the new usage data and task
    USAGE_POOL[model_id] = {
        **(USAGE_POOL[model_id] if model_id in USAGE_POOL else {}),
        sid: {"updated_at": current_time},
    }

    # Broadcast the usage data to all clients
    await sio.emit("usage", {"models": get_models_in_use()})


@sio.event
async def connect(sid, environ, auth):
    """Connect event."""
    user = None
    if auth and "token" in auth:
        data = decode_token(auth["token"])

        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

        if user:
            SESSION_POOL[sid] = user.model_dump()
            if user.id in USER_POOL:
                USER_POOL[user.id] = USER_POOL[user.id] + [sid]
            else:
                USER_POOL[user.id] = [sid]

            # print(f"user {user.name}({user.id}) connected with session ID {sid}")
            await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})  # type: ignore
            await sio.emit("usage", {"models": get_models_in_use()})


@sio.on("user-join")  # type: ignore
async def user_join(sid, data):
    """User join event."""
    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    data = decode_token(auth["token"])
    if data is None or "id" not in data:
        return

    user = Users.get_user_by_id(data["id"])
    if not user:
        return

    SESSION_POOL[sid] = user.model_dump()
    if user.id in USER_POOL:
        USER_POOL[user.id] = USER_POOL[user.id] + [sid]
    else:
        USER_POOL[user.id] = [sid]

    # Join all the channels
    channels = Channels.get_channels_by_user_id(user.id)
    logger.debug(f"{channels=}")
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")

    # print(f"user {user.name}({user.id}) connected with session ID {sid}")

    await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})  # type: ignore
    return {"id": user.id, "name": user.name}


@sio.on("join-channels")  # type: ignore
async def join_channel(sid, data):
    """Join the channels."""
    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    data = decode_token(auth["token"])
    if data is None or "id" not in data:
        return

    user = Users.get_user_by_id(data["id"])
    if not user:
        return

    # Join all the channels
    channels = Channels.get_channels_by_user_id(user.id)
    logger.debug(f"{channels=}")
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")


@sio.on("channel-events")  # type: ignore
async def channel_events(sid, data):
    """Channel events."""
    room = f"channel:{data['channel_id']}"
    participants = sio.manager.get_participants(
        namespace="/",
        room=room,
    )

    sids = [sid for sid, _ in participants]
    if sid not in sids:
        return

    event_data = data["data"]
    event_type = event_data["type"]

    if event_type == "typing":
        await sio.emit(
            "channel-events",
            {
                "channel_id": data["channel_id"],
                "message_id": data.get("message_id", None),
                "data": event_data,
                "user": UserNameResponse(**SESSION_POOL[sid]).model_dump(),
            },
            room=room,
        )


@sio.on("user-list")  # type: ignore
async def user_list(sid):
    """User list event."""
    await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})  # type: ignore


@sio.event
async def disconnect(sid):
    """Disconnect event."""
    if sid in SESSION_POOL:
        user = SESSION_POOL[sid]
        del SESSION_POOL[sid]

        user_id = user["id"]
        USER_POOL[user_id] = [_sid for _sid in USER_POOL[user_id] if _sid != sid]

        if len(USER_POOL[user_id]) == 0:
            del USER_POOL[user_id]

        await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})  # type: ignore


def get_event_emitter(request_info):
    """Get the event emitter function."""

    async def __event_emitter__(event_data):
        user_id = request_info["user_id"]
        session_ids = list(
            set(USER_POOL.get(user_id, []) + [request_info["session_id"]])  # type: ignore
        )

        for session_id in session_ids:
            await sio.emit(
                "chat-events",
                {
                    "chat_id": request_info["chat_id"],
                    "message_id": request_info["message_id"],
                    "data": event_data,
                },
                to=session_id,
            )

        if "type" in event_data and event_data["type"] == "status":
            Chats.add_message_status_to_chat_by_id_and_message_id(
                request_info["chat_id"],
                request_info["message_id"],
                event_data.get("data", {}),
            )

        if "type" in event_data and event_data["type"] == "message":
            message = Chats.get_message_by_id_and_message_id(
                request_info["chat_id"],
                request_info["message_id"],
            )

            content = message.get("content", "")  # type: ignore
            content += event_data.get("data", {}).get("content", "")

            Chats.upsert_message_to_chat_by_id_and_message_id(
                request_info["chat_id"],
                request_info["message_id"],
                {
                    "content": content,
                },
            )

        if "type" in event_data and event_data["type"] == "replace":
            content = event_data.get("data", {}).get("content", "")

            Chats.upsert_message_to_chat_by_id_and_message_id(
                request_info["chat_id"],
                request_info["message_id"],
                {
                    "content": content,
                },
            )

    return __event_emitter__


def get_event_call(request_info):
    """Get the event call function."""

    async def __event_call__(event_data):
        response = await sio.call(
            "chat-events",
            {
                "chat_id": request_info["chat_id"],
                "message_id": request_info["message_id"],
                "data": event_data,
            },
            to=request_info["session_id"],
        )
        return response

    return __event_call__


def get_user_id_from_session_pool(sid):
    """Get the user id from the session pool."""
    user = SESSION_POOL.get(sid)
    if user:
        return user["id"]
    return None


def get_user_ids_from_room(room):
    """Get the user ids from the room."""
    active_session_ids = sio.manager.get_participants(
        namespace="/",
        room=room,
    )

    active_user_ids = list(
        set(
            [SESSION_POOL.get(session_id[0])["id"] for session_id in active_session_ids]  # type: ignore
        )
    )
    return active_user_ids


def get_active_status_by_user_id(user_id):
    """Get the active status by user id."""
    return user_id in USER_POOL
