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