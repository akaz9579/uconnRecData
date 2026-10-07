import csv
import math
from datetime import datetime
from pathlib import Path
from threading import Lock

import socketio

SPACE_ID = "86fb9e11-6795-4e98-ac36-67262d509fc6"
BASE_URL = "https://app.safespace.io"
SOCKET_PATH = "veart/socket.io"

CSV_PATH = Path(__file__).resolve().parent / "safespace_occupancy.csv"

max_capacity = 1000
occupancy_write_lock = Lock()

sio = socketio.Client(
    reconnection=False,
    ssl_verify=False,
)


def rating(percent: int) -> str:
    if percent < 20:
        return "Golden"
    if percent < 30:
        return "Perfect"
    if percent < 40:
        return "Good"
    if percent < 50:
        return "Ehh bad"
    if percent < 60:
        return "Not worth it"
    return "Horrible"


def append_to_csv(percent: int, result_rating: str) -> None:
    now = datetime.now()

    row = {
        "Date": now.strftime("%Y-%m-%d"),
        "Day of Week": now.strftime("%A"),
        "Hour": now.strftime("%I:%M %p"),
        "Occupancy Percentage": percent,
        "Rating": result_rating,
    }

    file_exists = CSV_PATH.exists()

    with CSV_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "Date",
                "Day of Week",
                "Hour",
                "Occupancy Percentage",
                "Rating",
            ],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)

    print(f"Saved to: {CSV_PATH}")


@sio.event
def connect():
    print("Connected")

    sio.emit("manualoccupancy:subscribe", SPACE_ID)
    sio.emit("manualoccupancy:spaceupdate-subscribe", SPACE_ID)


@sio.on("manualoccupancy:spaceupdate")
def space_update(data):
    global max_capacity

    try:
        capacity = data["space"]["maxCapacity"]
        max_capacity = int(capacity)
        print(f"Max capacity: {max_capacity}")
    except (KeyError, TypeError, ValueError):
        pass


@sio.on("manualoccupancy:data")
def occupancy_data(data):
    # Socket.IO can invoke this handler concurrently for duplicate events.
    # Only the first callback in this process is allowed to continue.
    if not occupancy_write_lock.acquire(blocking=False):
        return

    occupants = int(data["occupants"])

    percent = min(
        100,
        math.floor((occupants / max_capacity) * 100)
    )

    result_rating = rating(percent)

    print()
    print(f"Occupants: {occupants}")
    print(f"Capacity: {max_capacity}")
    print(f"Occupancy: {percent}%")
    print(f"Rating: {result_rating}")

    append_to_csv(percent, result_rating)

    sio.disconnect()


@sio.event
def disconnect():
    print("Disconnected")


sio.connect(
    BASE_URL,
    socketio_path=SOCKET_PATH,
    transports=["websocket", "polling"],
)

sio.wait()
