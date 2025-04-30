import io
import sys
import json
import logging
import uvicorn
import keyboard
import requests
import threading
import websocket
import tkinter as tk
from app import server
import customtkinter as ctk
from app.server import app as fastapi_app
from app.server import latest_presses, press_history, user_connections

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.base_title = "Party Games App"
        self.title(self.base_title)
        self.geometry("800x600")
        self.minsize(800, 600)  # Minimum window size set

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (MainScreen, ConnectScreen, GuestScreen, HostScreen, HistoryScreen):
            frame = F(self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.current_frame = None
        self.show_frame(MainScreen)

    def show_frame(self, cont):
        current_frame = self.current_frame

        # Stop server if leaving HostScreen but not for HistoryScreen
        if isinstance(current_frame, HostScreen) and cont != HistoryScreen:
            current_frame.stop_server()

        if isinstance(current_frame, HostScreen) and not isinstance(cont, HostScreen):
            current_frame.stop_server_connection()

        frame = self.frames[cont]
        frame.tkraise()
        self.current_frame = frame

        # Start server if entering HostScreen but not from HistoryScreen
        if isinstance(frame, HostScreen) and not isinstance(current_frame, HistoryScreen):
            print(f"\nApp:\tEntered HostScreen")
            frame.start_server()

        # Update history screen if we're showing it
        if isinstance(frame, HistoryScreen):
            frame.update_history()

        if isinstance(frame, HostScreen):
            frame.start_server_connection()

        # Update window title
        if isinstance(frame, (MainScreen, ConnectScreen)):
            self.title(self.base_title)
        elif isinstance(frame, HostScreen) or isinstance(frame, HistoryScreen):
            self.title(f"{self.base_title} - Hosting Game")
        elif isinstance(frame, GuestScreen):
            frame.update_title(disconnected=True)


class MainScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        self.master = master

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.grid_rowconfigure((0, 1, 2), weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # Fonts (initial size, will update dynamically)
        self.label_font = ctk.CTkFont(size=16)
        self.button_font = ctk.CTkFont(size=14)

        # Label
        self.label = ctk.CTkLabel(content_frame, text="Choose Your Role", font=self.label_font)
        self.label.grid(row=0, column=0, pady=(0, 10), sticky="s")

        # Buttons
        self.host_button = ctk.CTkButton(content_frame, text="Host", command=lambda: master.show_frame(HostScreen), height=36, font=self.button_font)
        self.host_button.grid(row=2, column=0, padx=50, pady=(5, 0), sticky="nsew")

        self.guest_button = ctk.CTkButton(content_frame, text="Guest", command=lambda: master.show_frame(ConnectScreen), height=36, font=self.button_font)
        self.guest_button.grid(row=1, column=0, padx=50, pady=(0, 5), sticky="nsew")

        # Bind resize event
        self.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        width = event.width
        height = event.height

        # Adjust font sizes based on window size
        new_label_size = max(12, int(height / 25))
        new_button_size = max(10, int(height / 30))

        self.label_font.configure(size=new_label_size)
        self.button_font.configure(size=new_button_size)


class ConnectScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        # Grid Layout: Keep centered, but control height better
        self.grid_rowconfigure((0, 6), weight=1)  # Top & Bottom stretch
        self.grid_rowconfigure((1, 2, 3, 4, 5), weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.label_font = ctk.CTkFont(size=16)
        self.button_font = ctk.CTkFont(size=14)
        self.entry_font = ctk.CTkFont(size=14)

        # Label
        self.label = ctk.CTkLabel(self, text="Connect", font=self.label_font)
        self.label.grid(row=1, column=0, pady=(0, 5), sticky="s")

        # IP Entry
        self.ip_entry = ctk.CTkEntry(self, placeholder_text="Enter IP or Domain", height=36, font=self.entry_font)
        self.ip_entry.grid(row=2, column=0, padx=50, pady=(0, 2), sticky="ew")  # 2px between entries

        # Name Entry
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter Your Name (No Spaces)", height=36, font=self.entry_font)
        self.name_entry.grid(row=3, column=0, padx=50, pady=(0, 5), sticky="ew")
        self.name_entry.bind("<KeyRelease>", self.validate_name)

        # Button Frame to Equalize Size
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, padx=50, pady=(5, 0), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.confirm_button = ctk.CTkButton(button_frame, text="Confirm", command=self.confirm, font=self.button_font, height=40)
        self.confirm_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.back_button = ctk.CTkButton(button_frame, text="Back", command=lambda: master.show_frame(MainScreen), font=self.button_font, height=40)
        self.back_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.bind("<Configure>", self.on_resize)

    def validate_name(self, event=None):
        current_text = self.name_entry.get()
        if " " in current_text:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, current_text.replace(" ", ""))

    def confirm(self):
        ip = self.ip_entry.get()
        name = self.name_entry.get()
        if ip and name:
            print(f"Connecting to {ip} as {name}")
            guest_screen = self.master.frames[GuestScreen]
            guest_screen.connect_to_server(ip, name)
            self.master.after(0, lambda: self.master.show_frame(GuestScreen))  # Delay to ensure screen updates
        else:
            print("IP and Name required.")


    def on_resize(self, event):
        height = event.height
        new_label_size = max(12, int(height / 25))
        new_button_size = max(10, int(height / 30))
        new_entry_size = max(12, int(height / 28))

        self.label_font.configure(size=new_label_size)
        self.button_font.configure(size=new_button_size)
        self.entry_font.configure(size=new_entry_size)


class GuestScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.ws = None
        self.ws_thread = None
        self.name = ""
        self.ip = ""
        self.space_listener_thread = None
        self.space_listener_active = False

        # Remove top row stretch
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure((1, 2, 3, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.label_font = ctk.CTkFont(size=16)
        self.button_font = ctk.CTkFont(size=14)

        self.label = ctk.CTkLabel(self, text="Game", font=self.label_font)
        self.label.grid(row=0, column=0, pady=10, sticky="s")

        self.textbox = ctk.CTkTextbox(self)
        self.textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.textbox.configure(state="disabled")

        # Add a new textbox for connected users
        self.users_textbox = ctk.CTkTextbox(self)
        self.users_textbox.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.users_textbox.configure(state="disabled")

        self.press_button = ctk.CTkButton(self, text="Press", command=self.send_press, font=self.button_font)
        self.press_button.grid(row=3, column=0, padx=50, pady=5, sticky="nsew")

        self.back_button = ctk.CTkButton(self, text="Back", command=self.disconnect, font=self.button_font)
        self.back_button.grid(row=4, column=0, padx=50, pady=5, sticky="nsew")

        self.bind("<Configure>", self.on_resize)

    def connect_to_server(self, ip, name):
        self.name = name
        self.ip = ip
        ws_url = f"ws://{ip}:6969/{name}"
        print(f"App:\tConnecting to {ws_url}")
        self.update_title(disconnected=True)
        self.ws_thread = threading.Thread(target=self.run_ws, args=(ws_url,), daemon=True)
        self.ws_thread.start()

        # Start global spacebar listener in a separate thread
        if not self.space_listener_active:
            self.space_listener_active = True
            self.space_listener_thread = threading.Thread(target=self.listen_for_spacebar, daemon=True)
            self.space_listener_thread.start()

    def listen_for_spacebar(self):
        keyboard.add_hotkey('space', self.send_press)
        while self.space_listener_active:
            keyboard.wait('esc')  # Just keeps the thread alive, not used for actual action.

    def update_title(self, disconnected=False):
        if disconnected:
            self.master.title(f"{self.master.base_title} - Disconnected")
        else:
            self.master.title(f"{self.master.base_title} - In Game as {self.name} ({self.ip})")

    def run_ws(self, ws_url):
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("type") == "update":
                    latest_presses = data.get("latest_presses", [])
                    self.update_textbox(latest_presses)
                elif data.get("type") == "users":
                    users = data.get("connected_users", [])
                    self.update_users_textbox(users)
                else:
                    self.append_text(f"Unknown message: {data}")
            except Exception as e:
                self.append_text(f"Error parsing message: {message} ({e})")

        def on_error(ws, error):
            self.master.after(0, lambda: self.update_title(disconnected=True))
            self.append_text(f"Connection error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.master.after(0, lambda: self.update_title(disconnected=True))
            self.append_text("Connection closed")

        def on_open(ws):
            self.master.after(0, lambda: self.update_title(disconnected=False))
            self.append_text("Connection opened")
            connect_msg = {
                "user": self.name,
                "action": "on_connect",
                "payload": {"name": self.name}
            }
            ws.send(json.dumps(connect_msg))

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        self.ws.run_forever()

    def update_textbox(self, latest_presses):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", tk.END)
        for press in latest_presses:
            self.textbox.insert(tk.END, press + "\n")
        self.textbox.configure(state="disabled")

    def append_text(self, text):
        self.textbox.configure(state="normal")
        self.textbox.insert(tk.END, text + "\n")
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def send_press(self):
        if self.ws:
            message = {
                "user": self.name,
                "action": "button_press",
                "payload": None
            }
            try:
                self.ws.send(json.dumps(message))
                print(f"Sent: {message}")
            except Exception as e:
                print(f"Failed to send: {e}")

    def disconnect(self):
        if self.ws:
            self.ws.close()
        self.space_listener_active = False  # Stop the listener thread
        keyboard.unhook_all_hotkeys()
        self.master.show_frame(MainScreen)

    def on_resize(self, event):
        height = event.height
        new_label_size = max(12, int(height / 25))
        new_button_size = max(10, int(height / 30))
        self.label_font.configure(size=new_label_size)
        self.button_font.configure(size=new_button_size)
    
    def update_users_textbox(self, users):
        self.users_textbox.configure(state="normal")
        self.users_textbox.delete("1.0", tk.END)
        for user in users:
            self.users_textbox.insert(tk.END, user + "\n")
        self.users_textbox.configure(state="disabled")


class HostScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.server_thread = None
        self.server = None
        self.server_running = False
        self.connected_users_textbox = None  # New textbox reference
        self.ws = None
        self.ws_thread = None
        self.name = "Host"  # You can set this to any name
        self.ip = "127.0.0.1"  # Assuming host is local, adjust as needed

        # Fonts
        self.label_font = ctk.CTkFont(size=16)
        self.button_font = ctk.CTkFont(size=14)

        # UI Layout
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="Host Screen", font=self.label_font)
        self.label.grid(row=0, column=0, pady=10, sticky="s")

        # Split Row 1 into 2 columns with matching background
        split_frame = ctk.CTkFrame(self, fg_color="transparent")  # Transparent background
        split_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        split_frame.grid_columnconfigure((0, 1), weight=1)
        split_frame.grid_rowconfigure(0, weight=1)

        # Left: Latest Presses Textbox
        self.textbox = ctk.CTkTextbox(split_frame)
        self.textbox.grid(row=0, column=0, padx=5, sticky="nsew")
        self.textbox.configure(state="disabled")

        # Right: Connected Users Textbox
        self.connected_users_textbox = ctk.CTkTextbox(split_frame)
        self.connected_users_textbox.grid(row=0, column=1, padx=5, sticky="nsew")
        self.connected_users_textbox.configure(state="disabled")

        self.console = ctk.CTkTextbox(self)
        self.console.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.console.configure(state="disabled")
        sys.stdout = TextRedirector(self.console)
        sys.stderr = TextRedirector(self.console)
        self.setup_uvicorn_logging()

        # Buttons
        self.save_button = ctk.CTkButton(self, text="Save to History", command=self.save_to_history, font=self.button_font)
        self.save_button.grid(row=3, column=0, padx=50, pady=5, sticky="nsew")

        self.history_button = ctk.CTkButton(self, text="View History", command=lambda: master.show_frame(HistoryScreen), font=self.button_font)
        self.history_button.grid(row=4, column=0, padx=50, pady=5, sticky="nsew")

        self.back_button = ctk.CTkButton(self, text="Back", command=lambda: master.show_frame(MainScreen), font=self.button_font)
        self.back_button.grid(row=5, column=0, padx=50, pady=5, sticky="nsew")

        self.bind("<Configure>", self.on_resize)

    def connect_to_server(self):
        ws_url = f"ws://{self.ip}:6969/{self.name}"
        self.ws_thread = threading.Thread(target=self.run_ws, args=(ws_url,), daemon=True)
        self.ws_thread.start()

    def start_server_connection(self):
        if not self.ws_thread:
            ws_url = f"ws://{self.ip}:6969/{self.name}"
            print(f"App:\tConnecting to {ws_url} as Host")
            self.ws_thread = threading.Thread(target=self.run_ws, args=(ws_url,), daemon=True)
            self.ws_thread.start()

    def stop_server_connection(self):
        if self.ws:
            self.ws.close()
            self.ws = None
        self.ws_thread = None
        print("App:\tHost WebSocket connection closed.")

    def run_ws(self, ws_url):
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("type") == "users":
                    users = data.get("connected_users", [])
                    self.update_connected_users(users)
                elif data.get("type") == "update":
                    latest = data.get("latest_presses", [])
                    self.update_latest_presses(latest)
            except Exception as e:
                print(f"App:\tError parsing message: {e}")

        def on_open(ws):
            print("App:\tHost WebSocket connected")

        def on_error(ws, error):
            print(f"App:\tWebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print("App:\tWebSocket closed")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        self.ws.run_forever()

    def update_connected_users(self, users):
        self.connected_users_textbox.configure(state="normal")
        self.connected_users_textbox.delete("1.0", tk.END)
        for user in users:
            self.connected_users_textbox.insert(tk.END, user + "\n")
        self.connected_users_textbox.configure(state="disabled")

    def update_latest_presses(self, latest_presses):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", tk.END)
        for press in latest_presses:
            self.textbox.insert(tk.END, press + "\n")
        self.textbox.configure(state="disabled")

    def save_to_history(self):
        def post_history():
            try:
                response = requests.post("http://127.0.0.1:6969/save_to_history")
                print(f"App:\tStatus: {response.json().get('message')}")
            except Exception as e:
                print(f"App:\tError saving to history: {e}")

        threading.Thread(target=post_history, daemon=True).start()

    def update_text(self, text):
        self.textbox.configure(state="normal")
        self.textbox.insert(tk.END, text + "\n")
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def on_resize(self, event):
        height = event.height
        new_label_size = max(12, int(height / 25))
        new_button_size = max(10, int(height / 30))
        self.label_font.configure(size=new_label_size)
        self.button_font.configure(size=new_button_size)

    def setup_uvicorn_logging(self):
        logger = logging.getLogger("uvicorn")
        handler = logging.StreamHandler(TextRedirector(self.console))
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)

    def start_server(self):
        if not self.server_running:
            config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=6969, log_level="info")
            self.server = uvicorn.Server(config)

            def run_server():
                self.server_running = True
                self.server.run()
                self.server_running = False

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            print("App:\tFastAPI server started.")

    def stop_server(self):
        if self.server_running and self.server:
            self.server.should_exit = True  # Graceful stop signal
            print("App:\tStopping FastAPI server...")


class HistoryScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.grid_rowconfigure((0, 1), weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.label_font = ctk.CTkFont(size=16)
        self.button_font = ctk.CTkFont(size=14)

        self.label = ctk.CTkLabel(self, text="Press History", font=self.label_font)
        self.label.grid(row=0, column=0, pady=10, sticky="s")

        self.textbox = ctk.CTkTextbox(self)
        self.textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.textbox.configure(state="disabled")

        self.back_button = ctk.CTkButton(self, text="Back to Host", command=self.back_to_host, font=self.button_font)
        self.back_button.grid(row=2, column=0, padx=50, pady=5, sticky="nsew")

        self.bind("<Configure>", self.on_resize)

    def back_to_host(self):
        self.master.show_frame(HostScreen)

    def on_resize(self, event):
        height = event.height
        new_label_size = max(12, int(height / 25))
        new_button_size = max(10, int(height / 30))
        self.label_font.configure(size=new_label_size)
        self.button_font.configure(size=new_button_size)

    def update_history(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", tk.END)
        for idx, presses in enumerate(press_history, 1):
            self.textbox.insert(tk.END, f"Round {idx}: {', '.join(presses)}\n")
        self.textbox.configure(state="disabled")


class TextRedirector(io.StringIO):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def write(self, s):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.configure(state="disabled")

    def flush(self):
        pass