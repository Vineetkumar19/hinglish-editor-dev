# Running everything from Telegram

The terminal is a bad place to run something that works all day and needs a
yes or no from you at unpredictable moments. Telegram is a good place: it is
already on your phone, it keeps history forever, and a button is easier than
remembering an approval id.

This is the same approval gate as the dashboard and the command line, not a
way around it. Nothing is sent until you tap **Approve**.

## One-time setup, about five minutes

**1. Make the bot.**
Open Telegram, search for **@BotFather**, send `/newbot`, and answer the two
questions it asks. It gives you a token that looks like
`123456789:AAHk...`. Copy it.

**2. Put the token in your settings.**
In the `Agents` folder, open `.env` (make one by copying `.env.example` if it
is not there) and add the line:

```
TELEGRAM_BOT_TOKEN=123456789:AAHk...
```

**3. Make the group.**
In Telegram, make a new group. Call it anything. Add your bot to it.
Then open the group, go to **Edit → Topics**, and turn Topics **on**.
Finally, open the member list, tap your bot, and make it an **administrator**
with the **Manage Topics** permission.

A bot cannot create a group by itself — Telegram does not allow it, a bot can
only ever be added by a person. That is why this step is yours. Everything
after it is the bot's job.

**4. Start it.**

```
python run.py telegram
```

Leave that window open, then send `/start` in your group. The bot creates four
topics and tells you it is ready:

```
Sponsorship     brand and sponsorship outreach
Video Clients   video editing client outreach
Dev Sales       development enquiries and quotes
Jobs            job hunting, resumes and interviews
```

Each agent posts only in its own topic, so the four never mix.

## Commands

| Command | What it does |
|---|---|
| `/status` | What each agent is doing and what is waiting on you |
| `/pending` | Everything waiting for a decision, each with buttons |
| `/run jobs` | Run the job agent now. Also `sponsorship`, `video`, `dev` |
| `/jobs` | Jobs it found recently, with the skills each one asks for |
| `/exp 1` | Set your years of experience. Filters everything above it out |
| `/roles` | Choose which kinds of job to look for |
| `/leads` | Companies and creators it found recently |
| `/resume` | Sends you the tailored resume PDFs |
| `/doctor` | Checks the setup is healthy |
| `/id` | Your Telegram user id and this chat's id |
| `/help` | The list above |

## Approving things

When an agent wants to send an email or apply to a job, it stops and posts the
whole thing in the right topic with buttons. Tap **Approve** and it carries
on. Tap **Reject** and it moves to the next one.

A job card gets a third button, **Send me the resume**, which hands you the PDF
built for that exact job so you can read it before deciding rather than after,
and a fourth that opens the application page directly.

After you tap, the buttons are replaced with **APPROVED** or **REJECTED**, so
you can scroll back and see what you decided and when. Tapping an old message
again does nothing — a decision is made once.

## Who can use the bot

The first person to send `/start` becomes the owner, and the bot ignores
everyone else. If you would rather pin it explicitly, send `/id` to see your
Telegram user id and put it in `.env`:

```
TELEGRAM_OWNER_ID=123456789
```

This matters. Anyone who could drive the bot could approve your outgoing email.

## Getting every event on your phone

By default the bot only speaks when you speak to it. To have the agents push
their own updates — a brand replied, an interview was scheduled — add
`telegram` to the notification channels in `.env`:

```
NOTIFY_CHANNELS=console,store,telegram
```

## If something goes wrong

**"TELEGRAM_BOT_TOKEN is not set"** — step 2 above.

**"This group does not have Topics turned on"** — Edit → Topics in the group,
then send `/start` again. The bot still works without topics; all four agents
just share one chat.

**"I could not create the topic"** — the bot is not an admin, or does not have
the Manage Topics permission. Fix that and send `/start` again.

**The bot does not answer at all** — the `python run.py telegram` window has to
stay open. Close it and the bot goes quiet until you start it again.

**It answers someone else but not you** — someone else sent `/start` first and
owns it. Set `TELEGRAM_OWNER_ID` in `.env` to your own id and restart.
