# 🚂 Train Tickets Bot for pass.rw.by

A Telegram bot that helps you find available train tickets on the Belarusian Railways website (pass.rw.by).

## 🌟 Features

- **Real-time monitoring** of ticket availability
- **Instant notifications** when tickets become available
- **Multiple simultaneous searches** (up to 3 concurrent searches)
- **Simple commands** with intuitive interface
- **Graceful shutdown** messages users when bot is stopped and stops tasks

## 🛠 Technologies Used

- Python 3.12
- python-telegram-bot
- aiohttp for asynchronous HTTP requests
- BeautifulSoup for HTML parsing
- structlog for structured logging
- pytest for testing

### Running the Bot

```bash
  uv run main.py
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
3. Bot continuously checks ticket availability every 5 minutes
4. You'll receive instant notification when tickets become available
5. Use "Cancel" to stop searching or "Another ticket" to add more searches

### Notes:

- Station names should match exactly with pass.rw.by
- Maximum 3 concurrent searches per user
- Bot automatically stops all searches when shut down

### Screenshots:

<img width="377" height="286" alt="image" src="https://github.com/user-attachments/assets/f7bcb17b-4f1d-44b1-bf84-6652bca1b140" />

---

<img width="437" height="341" alt="image" src="https://github.com/user-attachments/assets/55895803-bba5-4394-a445-e967e3d522a8" />

---

<img width="437" height="341" alt="image" src="https://github.com/user-attachments/assets/a82fe23c-48c2-447b-9bfe-4e208d4063f9" />

---

<img width="437" height="146" alt="image" src="https://github.com/user-attachments/assets/d72940c9-9800-42bb-90fd-b7d54b79e0da" />

---

<img width="437" height="254" alt="image" src="https://github.com/user-attachments/assets/e3652eb2-8161-4875-92e8-5f2d6e184c1b" />
