# 🚂 Train Tickets Bot for pass.rw.by

A Telegram bot that helps you find available train tickets on the Belarusian Railways website (pass.rw.by).
You can find bot at @train_tickets_passrw_bot

## 🌟 Features

- **Real-time monitoring** of ticket availability
- **Instant notifications** when tickets become available
- **Multiple simultaneous searches** can search for an unlimited number of tickets
- **Simple commands** with intuitive interface
- **Graceful shutdown** saves the state when the system is restarted

## 🛠 Technologies Used

- Python 3.12
- python-telegram-bot
- aiohttp for asynchronous HTTP requests
- psycopg2 for db
- BeautifulSoup for HTML parsing
- structlog for structured logging
- pytest for testing

### Running the Bot

```bash
  uv run main.py
```

or with docker compose

```bash
  docker compose up --build
```

## 📋 Usage

### Basic Commands:

- `/start` - Show welcome message and instructions
- `From To Date Time` - Start ticket search (e.g., `Толочин  Минск-Пассажирский 2024-12-25 08:00`)
- `Cancel Button` - Stop all active searches
- `Another ticket Button` - Add new search while keeping existing on

### How It Works:

1. Send your search request in the specified format
2. Bot will validate your input and confirm the search
3. It saves your request in db
4. Then, Bot continuously checks ticket availability every n seconds
5. If someone with ticket cancels his ticket (which happens quite often),
   you will receive an instant notification that a ticket has become available
6. Use "Cancel" to stop searching or "Another ticket" to add more searches

### Notes:

- Station names and time values should match exactly with pass.rw.by

### Screenshots:

<img width="418" height="245" alt="image" src="https://github.com/user-attachments/assets/605639a2-beb1-4b0a-8a1e-172743cd3811" />

---

<img width="418" height="203" alt="image" src="https://github.com/user-attachments/assets/805120d0-6f21-4ba3-816f-047be3fa4dda" />

---

<img width="418" height="308" alt="image" src="https://github.com/user-attachments/assets/fbf361e0-75ab-4e08-83e5-5799a1a984ac" />

---

<img width="418" height="320" alt="image" src="https://github.com/user-attachments/assets/5c264a49-ee80-4dd7-9778-bfab38931e3a" />

---

<img width="418" height="228" alt="image" src="https://github.com/user-attachments/assets/b4742d23-f797-4b40-ab3a-34a9a820bc7b" />
