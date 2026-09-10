# Surfaces Tiles UK - Sophie Chatbot Frontend (PHP Component)

A self-contained, modular PHP chatbot widget built for **Surfaces Tiles UK**. Designed to match the modern "Sophie" assistant UI with zero external dependencies and guaranteed CSS scoping.

---

## 📸 Design & UI Features

- **Exact Match to Reference Design**:
  - Warm stone palette (`#FAF8F5`, `#EFECE6`, `#111111`).
  - Circular avatar with 4-point sparkle badge.
  - Header with bot status ("Online"), help modal button `(?)`, and close button `(✕)`.
  - Welcome greeting bubble:
    - `👋 Hi, I'm Sophie`
    - `Your Surfaces Tiles shopping assistant.`
    - `I can help you find the perfect tiles for your space.`
  - Pill-shaped quick suggestion buttons:
    - *Kitchen tiles*
    - *Bathroom tiles*
    - *Outdoor / patio*
    - *Show me best sellers*
  - "Try asking:" recommendation card with clickable quotes.
  - Footer input area with smile emoji picker, rounded input pill, and solid black circular send button.
- **Zero Style Conflicts**: All styles are strictly scoped under `#sophie-chat-widget`, `#sophie-chat-launcher`, and `.sophie-*`.
- **Fully Responsive**: Adapts seamlessly to desktop, tablet, and mobile screens.

---

## 📁 Directory Structure

```text
frontend/
├── config.php                  # Chatbot settings, branding, prompts, and backend URLs
├── api-proxy.php               # Secure PHP proxy connecting frontend to FastAPI backend
├── chatbot.php                 # Embeddable PHP widget component
├── index.php                   # Test harness & footer integration demo
├── README.md                   # Developer integration guide
└── assets/
    ├── css/
    │   └── sophie-chat.css     # Scoped stylesheet
    └── js/
        └── sophie-chat.js      # Zero-dependency vanilla JS controller
```

---

## 🚀 Quick Integration Guide

### Step 1: Copy Files
Copy the `frontend/` directory into your website project root or theme directory:
```bash
cp -r frontend/ /path/to/your/website/
```

### Step 2: Include in Footer
Open your website's footer template (e.g. `footer.php`, `layout.php`, or standard PHP page) and add this single line right before `</body>`:

```php
<?php include __DIR__ . '/frontend/chatbot.php'; ?>
```

### Step 3 (Optional): Customize Display Mode
By default, Sophie appears as a floating button in the bottom-right corner. If you want to embed Sophie inline directly inside a footer section or page column:

```php
<?php
$chatbot_mode = 'card'; // 'card' for inline embed, 'floating' for bottom-right widget
include __DIR__ . '/frontend/chatbot.php';
?>
```

---

## ⚙️ Configuration (`config.php`)

Edit `frontend/config.php` to adjust settings:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `api_url` | `http://127.0.0.1:8060` | URL of the Python FastAPI RAG backend |
| `bot_name` | `Sophie` | Assistant name |
| `bot_status` | `Online` | Subtitle displayed in header |
| `quick_suggestions` | 4 tile categories | Quick action buttons displayed on load |
| `try_asking` | 2 prompt quotes | Example queries displayed in the card |
| `request_timeout` | `30` | Timeout in seconds for backend calls |

---

## 🧪 Testing Locally

1. **Start the Python FastAPI Backend** (in the project root):
   ```bash
   conda activate surfaces-chatbot
   python main.py
   ```
   Backend will listen on `http://127.0.0.1:8060`.

2. **Start the PHP Development Server**:
   ```bash
   php -S 0.0.0.0:8000 -t frontend
   ```

3. **Open in Browser**:
   - `http://localhost:8000/?mode=card` (Footer Card Mode)
   - `http://localhost:8000/?mode=widget` (Floating Widget Mode)
