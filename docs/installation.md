# Installation Guide (for people who have never used Python before)

This guide assumes you have **never installed Python, never used a command
line, and never heard of MCP** before today. Every step is spelled out.

## What you're installing

TallyPrime MCP is a small program that runs quietly in the background and
lets an AI assistant (like Claude Desktop) ask your TallyPrime software
questions — "what's the trial balance", "show me last month's receipts" —
and get back real answers, without you ever having to export a report
yourself.

It runs entirely on your own computer. Nothing about your accounts leaves
your machine except to the AI assistant you've chosen to use, exactly the
same way it would if you'd typed the numbers into that assistant yourself.

## Step 1 — Install Python

TallyPrime MCP needs Python 3.11 or newer.

1. Go to [python.org/downloads](https://www.python.org/downloads/).
2. Click the big "Download Python" button. This downloads the latest
   version, which is fine.
3. Run the installer.
   - **Windows:** On the first installer screen, tick the box that says
     **"Add python.exe to PATH"** before clicking Install. This step is
     easy to miss and important — without it, the next steps won't work.
4. When installation finishes, open a **Command Prompt** (Windows: press
   the Windows key, type `cmd`, press Enter) and type:

   ```
   python --version
   ```

   You should see something like `Python 3.12.4`. If you instead see an
   error like "python is not recognized", Python either isn't installed or
   wasn't added to PATH — try re-running the installer and make sure that
   checkbox is ticked.

## Step 2 — Install TallyPrime MCP

In the same Command Prompt window, type:

```
pip install tallyprime-mcp
```

Press Enter and wait — you'll see some text scroll by as it downloads. When
it finishes and returns you to a normal prompt, it's installed.

Check it worked:

```
tallyprime-mcp --version
```

You should see `tallyprime-mcp 0.1.0` (or a newer version number).

## Step 3 — Turn on TallyPrime's connection gateway

TallyPrime MCP needs TallyPrime itself to have its "HTTP-XML gateway"
switched on — this is the feature that lets other programs on your computer
talk to Tally. See [tally-setup.md](tally-setup.md) for exactly where to
find this setting (it moves around a bit between TallyPrime versions).

## Step 4 — Check the connection

With TallyPrime open and a company loaded, go back to your Command Prompt
and type:

```
tallyprime-mcp test-connection
```

You should see:

```
Connected to TallyPrime at http://127.0.0.1:9000.
```

If instead you see an error about "could not connect", double check that:

- TallyPrime is actually open (not just installed).
- A company is loaded inside TallyPrime (File > select or open a company).
- The gateway setting from Step 3 is switched on.

## Step 5 — Connect it to your AI assistant

This part depends on which AI assistant you use:

- **Claude Desktop:** see [../examples/claude/README.md](../examples/claude/README.md).
- **Cursor:** see [../examples/cursor/README.md](../examples/cursor/README.md).
- **Something else:** see [../examples/generic/README.md](../examples/generic/README.md).

Once configured, restart your AI assistant app. You should now be able to
ask it things like "list my companies in Tally" or "show me the trial
balance" and have it answer using your real, local TallyPrime data.

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `python` / `pip` "not recognized" | Python wasn't added to PATH during install — re-run the Python installer and tick that box. |
| `tallyprime-mcp: command not found` | The folder pip installs scripts into isn't on your PATH. Try `python -m tallyprime_mcp.cli --version` instead, or reinstall Python with the PATH option checked. |
| "Could not connect to TallyPrime" | TallyPrime isn't running, no company is loaded, or the gateway isn't enabled — see Step 3/4 above. |
| Your AI assistant doesn't see any new tools after configuring it | Make sure you fully quit and reopened the assistant app (not just closed the window) after editing its configuration file. |

Still stuck? Please [open an issue](https://github.com/cavishal04/tallyprime-mcp/issues) — include your OS, Python version (`python --version`), and TallyPrime version.
