# Full Beginner Tutorial – Deploy & Run Your On-Chain Wallet Analyzer Bot

This guide is written for complete beginners.  
Follow the steps **one by one**. Do not skip any step.

---

## Part 1 – What You Need Before Starting

### 1.1 A computer
- Windows 10/11, Mac, or Linux – all work.

### 1.2 Internet connection
You need it to download Python and to talk to the Solana blockchain.

### 1.3 (Recommended) A better RPC
The free public Solana RPC is very slow and often rate-limits you.  
For real use, get a free Helius account (takes 2 minutes):

1. Go to → https://helius.dev
2. Sign up with email or Google
3. Create a free project
4. Copy the **RPC URL** (it looks like `https://mainnet.helius-rpc.com/?api-key=xxxxx`)

You will use this URL later.

---

## Part 2 – Install Python (Most Important Step)

### Windows

1. Go to https://www.python.org/downloads/
2. Click the big yellow **Download Python 3.12** (or newer) button
3. Run the installer
4. **VERY IMPORTANT**: On the first screen, tick the box that says  
   **“Add python.exe to PATH”**
5. Click “Install Now”
6. When finished, open **Command Prompt** (search for `cmd`) and type:

```bash
python --version
```

You should see something like `Python 3.12.x`.  
If you get an error, restart the computer and try again.

### Mac

1. Open Terminal
2. Install Homebrew (if you don’t have it):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Then install Python:

```bash
brew install python
```

4. Check:

```bash
python3 --version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
python3 --version
```

---

## Part 3 – Get the Bot Files

1. Download the zip file I prepared for you (`onchain-wallet-analyzer.zip`)
2. Extract it somewhere easy, for example:
   - Windows → `C:\Users\YourName\Desktop\onchain-wallet-analyzer`
   - Mac/Linux → `~/Desktop/onchain-wallet-analyzer`

You should now have a folder that contains:
- `run.py`
- `requirements.txt`
- `src/` folder
- `README.md`
- `.env.example`

---

## Part 4 – Create a Virtual Environment (Best Practice)

A virtual environment keeps the bot’s libraries separate from your system.

### Windows (Command Prompt)

```bash
cd Desktop\onchain-wallet-analyzer
python -m venv venv
venv\Scripts\activate
```

You will see `(venv)` appear at the beginning of the line. That means it is active.

### Mac / Linux

```bash
cd ~/Desktop/onchain-wallet-analyzer
python3 -m venv venv
source venv/bin/activate
```

You will also see `(venv)`.

**Important**: Every time you open a new terminal to use the bot, you must activate the venv again with the same command.

---

## Part 5 – Install the Required Libraries

While the virtual environment is activated, run:

```bash
pip install -r requirements.txt
```

This may take 1–3 minutes.  
If you see any red errors, copy the error and ask for help.

---

## Part 6 – Configure the Bot (RPC)

1. Copy the example config file:

**Windows**
```bash
copy .env.example .env
```

**Mac / Linux**
```bash
cp .env.example .env
```

2. Open the new `.env` file with any text editor (Notepad, VS Code, etc.)

3. Change the first line to your Helius (or QuickNode) RPC:

```env
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY_HERE
```

4. Save the file.

(You can leave the other settings as they are for now.)

---

## Part 7 – Run the Bot for the First Time

Make sure your virtual environment is still activated (`(venv)` is visible).

### Basic command

```bash
python run.py analyze PASTE_A_WALLET_ADDRESS_HERE
```

Example:

```bash
python run.py analyze 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
```

### Useful options

```bash
# Analyze multiple wallets
python run.py analyze WALLET1 WALLET2 WALLET3

# Go deeper (more recursion)
python run.py analyze WALLET --depth 7

# Ignore small transfers
python run.py analyze WALLET --min-sol 0.1

# Look at only last 30 days
python run.py analyze WALLET --lookback 30

# Force fresh data (ignore cache)
python run.py analyze WALLET --no-cache
```

---

## Part 8 – Understanding the Output

After the bot finishes you will see:

1. **Console summary** – how many wallets, main funders, mints found
2. **Tables** – list of main funders and wallets that minted tokens
3. **Funding tree** – simple text tree of who funded whom
4. **Two files** created inside the `reports/` folder:
   - `analysis_YYYYMMDD_HHMMSS.json` → full data (open with any text editor)
   - `graph_YYYYMMDD_HHMMSS.html` → **open this file in your browser** to see an interactive network graph

---

## Part 9 – Deploying on a VPS (Optional – for 24/7 use)

If you want the bot to live on a server instead of your personal computer:

### 9.1 Buy a cheap VPS
Good beginner options:
- Contabo (very cheap)
- DigitalOcean ($4–6/month)
- Hetzner
- Oracle Cloud (free tier)

Choose **Ubuntu 22.04 or 24.04**.

### 9.2 Connect to the server

```bash
ssh root@YOUR_SERVER_IP
```

### 9.3 Install everything on the server

```bash
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv git unzip -y

# Upload your zip (or use scp / FileZilla)
# Then:
unzip onchain-wallet-analyzer.zip
cd onchain-wallet-analyzer

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env          # paste your Helius RPC URL, then Ctrl+O → Enter → Ctrl+X
```

### 9.4 Run it

Same as before:

```bash
python run.py analyze WALLET_ADDRESS
```

### 9.5 Keep it running in the background (simple way)

Install `tmux`:

```bash
apt install tmux -y
tmux new -s analyzer
```

Inside tmux run your command.  
Then press `Ctrl+B` then `D` to detach.  
The bot keeps running even if you close the SSH window.

To come back later:

```bash
tmux attach -t analyzer
```

---

## Part 10 – Common Beginner Problems & Solutions

| Problem | Solution |
|---------|----------|
| `python` not recognized | You forgot to tick “Add to PATH”. Re-install Python and tick the box. |
| `pip` not found | Use `python -m pip install -r requirements.txt` |
| Rate limit / timeout errors | You are using the free public RPC. Switch to Helius. |
| `ModuleNotFoundError` | You forgot to activate the virtual environment (`venv\Scripts\activate`) |
| Permission denied on Linux | Never use `sudo pip`. Always use a virtual environment. |
| Graph HTML is empty | Install failed for `pyvis`. Run `pip install pyvis networkx` again. |

---

## Quick Cheat Sheet (copy-paste ready)

```bash
# 1. Go into the folder
cd onchain-wallet-analyzer

# 2. Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Run analysis
python run.py analyze YOUR_WALLET_HERE

# 4. Open the HTML graph
# Just double-click the .html file inside the reports/ folder
```

---

You now have everything you need.  
Start with Part 2 (install Python), then follow the rest in order.

If you get stuck at any step, copy the exact error message and ask — I’ll help you fix it.
