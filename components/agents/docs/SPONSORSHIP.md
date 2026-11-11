# The sponsorship agent

One agent, one brain, doing two things that are really the same thing.

**It finds brands.** It goes out to the internet - affiliate networks, the
Indian marketing press, the sponsor links in other cricket creators' video
descriptions - checks each one is real and Indian, and asks whether to add it
to your list.

**It pitches them.** It works down that list of 476 brands, agencies and
programmes, reads each site, finds a route to a human, writes the message for
that kind of deal, and asks before anything is sent.

They share a brain because they are the same judgement made at two moments.

```
python run.py telegram        # then /run sponsorship in the Sponsorship topic
python run.py run sponsorship # or from the terminal
python run.py discover        # same agent, with the web sweep forced on
```

A normal run is just the outreach. Once a week - or whenever you ask - it looks
at the web first, and anything it wants to add appears as its own card before
the outreach starts.

---

## What this agent is for

Brands paying you to promote them in a video. That is the whole point, and it
is what the list is ordered around.

**Paid promotion — 268 targets.** A brand pays for a read or an integration in
a cricket video. This is the goal and it goes first.

**Agencies — 41 targets.** Influencer and sports marketing agencies. Worth
pitching because they are the people who hand out paid campaigns, and they are
actively looking for creators rather than being pitched at. One agency that
likes your work can bring several paid deals a year.

**Barter — 143 targets.** Product instead of money. Not the goal, but worth
saying yes to early: each one is a real brand credit on the channel, and brands
check what you have done before before they pay you.

**Affiliate is switched off.** Earning a cut when a viewer buys through your
link is a different job - it makes you a salesman for someone else's catalogue.
The affiliate networks and shopping-link schemes have been removed from the
list entirely. If you ever want it, set
`SPONSORSHIP_DEAL_TYPES=cash,agency,barter,affiliate` in `.env`.

---

## Fill in your numbers as they grow

`profiles/creator.yaml` holds everything the agent is allowed to say about the
channel. It is filled in with your real figures — 1,213 subscribers, 2,014
followers, the Mumbai Indians documentary.

Two fields are deliberately at zero: average views per video, and the audience
split. With two videos published there is no meaningful average, and the agent
will not state a number it cannot stand behind. Fill them in once five or six
videos are up, and take the audience split from YouTube Studio > Audience.

`/mediakit` in Telegram shows what the emails currently claim and what is still
blank.

---

## What is on the list

476 entries, every domain checked live. Ordered so the agent meets the easiest
money first.

| Group | Count | Why they are there |
|---|---|---|
| Affiliate networks and marketplaces | 24 | One signup covers hundreds of merchants. EarnKaro and Cuelinks take anyone. |
| Cricket gear brands and retailers | 40 | Bat makers and cricket stores. A gear review is the video your audience came for, not an interruption. |
| Cricket apps, media, venues, academies, leagues | 60 | CricHeroes, SportVot, Hudle, state T20 leagues, coaching academies. Their users are your viewers. |
| Influencer platforms and agencies | 63 | Wobb, Hobo.Video, Creatorshala, Chtrbox, Grynow. The ones that take nano creators. |
| Sports nutrition and fitness | 33 | The heaviest creator-spending category in India, aimed at your exact demographic. |
| Men's grooming and personal care | 30 | The most reliable category for a young male audience. |
| Apparel, merch and fan goods | 31 | Cricket merch, streetwear, menswear — several with open creator squads. |
| Consumer tech and audio | 24 | boAt, Noise, Fire-Boltt, Boult. They seed product first, then buy integrations. |
| Food, snacks and beverages | 28 | Match-night is an occasion this category pays to own. |
| Fintech and money apps | 25 | Roughly a tenth of IPL creator spend, and most pay per signup. |
| OTT, audio and entertainment apps | 20 | Pocket FM and Kuku FM pay creators of almost any size for installs. |
| Gaming and esports | 15 | Free-to-play only. Hitwicket and Real Cricket are direct audience matches. |
| Creator tools | 44 | Hostinger, Surfshark, Epidemic Sound, vidIQ. They sponsor channels of every size and most publish a partnerships address. |
| Edtech, travel, telecom, home | 59 | The rest of the consumer spend. |

### What is deliberately not on the list

Real-money fantasy sports and betting. India's Promotion and Regulation of
Online Gaming Act (2025) made real-money gaming illegal, and Dream11, MPL,
My11Circle, Howzat and Gamezy can no longer run the campaigns they used to.
Promoting one is your legal problem, not theirs — which matters more now that
you have moved the channel off that niche deliberately.

The agent refuses the whole category in code - `BLOCKED_SEGMENTS` in
`agents/sponsorship/agent.py` for what is on the list, `BANNED` in
`agents/sponsorship/discover.py` for what the web sweep finds - and a test
fails if one ever appears. If you add brands yourself, that test is what protects you.

Also excluded after checking: doyourthng.com, which appears on most "top Indian
influencer platform" lists but now redirects to an offshore gambling domain,
and Winkl, whose domain is parked and for sale.

---

## Going out and finding new brands

A fixed list goes stale the day it ships. Every month new brands launch,
programmes open and competitors appear, so the agent has its own way onto the
internet. Four sources, none of which needs an API key:

**Cuelinks campaign directory.** An affiliate network's live listing of every
merchant currently paying commission - about 1,800 campaigns, payout printed
next to each. Every entry is an Indian brand spending money on promotion right
now. The strongest source there is, and it costs one page fetch.

**Who is already sponsoring other cricket channels.** It searches YouTube for
channels in your niche, opens their recent videos, and reads the sponsor links
out of the descriptions. A brand paying another cricket creator has already
decided a cricket audience is worth money, has a budget, and has someone whose
job is to place it.

**The Indian marketing press.** Social Samosa, Storyboard18, afaqs, Campaign
India, ET BrandEquity, Entrackr, Inc42. New campaigns and funding rounds appear
there first, which is how you reach a brand in the month it starts spending.

**Admitad**, filtered to India-targeted offers.

There is also a plain web search it can run for anything (`web_search`), using
open front-ends with no key. Those front-ends rate-limit and sometimes block,
so it tries several and takes the first that answers; if a `SEARCH_PROVIDER`
key is configured that is used as a guaranteed fallback. Nothing else depends
on it.

Turning a headline into a website needs no key either: it tries the domains a
brand of that name would own and keeps the one whose page actually reads as
that brand.

### The India filter

Your audience is Indian. A brand that does not ship to India, price in rupees
or market to Indians cannot use that audience, so pitching them wastes a slot.

It reads each site for what an Indian business cannot avoid publishing: rupee
prices, a +91 number, a GST number, an Indian address, Devanagari text,
Razorpay or UPI at checkout. Each signal is weak alone; the combination is not.
A site saying it does not ship to India is dropped outright. A site that
refuses to load at all is reported as exactly that, rather than as "not
Indian" - they are different things.

The score and the reasons both appear on the card.

### What it refuses outright

Real-money gaming and betting, checked three times over: the candidate's name,
the source's description of it, and the text of its own website. Brands already
on your list are dropped as duplicates rather than shown twice.

---

## The brain

This is the part that matters, and the part easiest to fake, so here is exactly
what happens.

**Every decision is stored as a labelled example.** Six or seven things about
each brand gain or lose evidence: where it was found, its segment, the kind of
deal, the domain type, how Indian it looked, whether it published an address.

**Both halves of the agent write to the same memory.** Adding a brand, refusing
to add one, approving a pitch, rejecting a pitch, sending one, a reply, a
bounce, an unsubscribe - all of it lands in one place, described in one
vocabulary. That is what makes it one brain rather than two: a reply from a
nutrition brand lifts both the next nutrition brand it finds on the web *and*
the nutrition brands still sitting on your list unpitched.

**What a brand did outweighs what you guessed.** A reply counts four times an
approval; a deal counts eight times. An unsubscribe counts three against.

| Event | Weight |
|---|---|
| A deal agreed | +8 |
| A brand replied, interested | +4 |
| You approved a pitch | +1.5 |
| You added a brand | +1 |
| A message went out | +0.5 |
| No way in could be found | −0.5 |
| You said no to adding it | −1 |
| You rejected a pitch | −1.5 |
| It bounced | −1.5 |
| A brand said no | −2 |
| Someone unsubscribed | −3 |

**The score is those shifts added up** - a beta-binomial per feature, summed as
log-odds. It moves on the very first example, so the agent is different after
one decision rather than a hundred, but one lucky approval is shrunk hard so it
cannot become a law.

**It changes who gets contacted next.** The queue is still ordered tier-first
and by the deals that pay soonest, but inside that the brain breaks the ties -
so the kinds of brand that actually reply drift to the top over time, and the
kinds that never do sink.

**It spends the next sweep where the last one paid off.** Each source has its
own record and the budget is allocated by Thompson sampling, so a source that
keeps producing brands you approve gets most of it while every source keeps a
real chance of being tried.

**It shows its working.** `/why nakpro.com` prints every feature and what it
did to the score:

```
Nakpro
nakpro.com

Score 68%   Indian 85%   Found by cuelinks

source=cuelinks      +0.41   (9 for, 1 against)
segment=nutrition    +0.22   (5 for, 2 against)
deal_type=barter     +0.18   (4 for, 1 against)
tld=com              -0.05   (3 for, 4 against)

A plus means things like this have worked out before.
```

A number asks to be trusted. The arithmetic underneath it can be argued with,
and arguing with it is how the agent learns. `/learned` shows the whole
picture.

---

## How it finds a way to reach them

Not every brand publishes an address, and the ones that do not are often worth
pitching anyway. So it works down a ladder and takes the first rung that holds:

1. An address published on their own site
2. A WhatsApp number they published themselves
3. Any other phone number on the site
4. Their own enquiry form, with the message ready to paste
5. A social profile to DM
6. A standard address pattern such as `partnerships@`, used only after checking
   the domain actually accepts mail, and labelled as a guess everywhere it
   appears

Anything the brand published itself outranks a guess — a guess can bounce, a
number on their contact page cannot.

Some sites refuse automated readers entirely. That is not a dead brand; it
falls through to rung 4, 5 or 6 like any other.

---

## What the approval card shows

```
Nakpro
nutrition  |  reachable
ASKING FOR A BARTER DEAL - product for a video

Email      hello@nakpro.com
Found      published on https://nakpro.com/pages/contact-us

Why them
Budget whey brand whose entire growth motor is micro-influencers

Subject: Cricket content collaboration - Nakpro
...
```

Buttons: **Approve**, **Reject**, **Show me the DM version**, and where it
applies **Open WhatsApp** (which opens the chat with the message already typed)
or **Open their form**.

The line in capitals is what you are actually asking for, because "join their
affiliate programme", "send me free product" and "pay me for a video" are three
different decisions.

---

## Email, WhatsApp, DM

Three messages are written for every target, because a WhatsApp message is not
an email with the paragraphs taken out.

The **email** opens on something specific from their own site, says what the
channel is, states only the numbers in your profile, makes the argument for
that segment, links your work, and ends with one question — the right question
for that kind of deal.

The **WhatsApp message** is three lines and a question. The **Instagram DM** is
shorter still.

The agent sends email itself once you approve. It cannot send WhatsApp or fill
in a web form, so for those it marks the lead `ready_to_send` and hands you the
finished message and a one-tap link. `/brands` lists everything waiting on you.

---

## Commands

| Command | What it does |
|---|---|
| `/run sponsorship` | Work through the next batch, sweeping the web first if a sweep is due |
| `/discover` | The same agent with the sweep forced on now |
| `/discover cuelinks` | One source only |
| `/brands` | Pipeline, broken down by kind of deal |
| `/learned` | What your decisions have taught it |
| `/why nakpro.com` | The arithmetic behind one score |
| `/mediakit` | What is still blank in your creator profile |
| `/pending` | Everything waiting for your approval |

---

## The contact sheet

```
python run.py sponsors                     # every target
python run.py sponsors --segment agency    # one group
python run.py sponsors --limit 40
```

Writes `data/sponsor_contacts.csv` — every brand, the emails and phone numbers
found, the route, the evidence, their Instagram and LinkedIn, and why they fit.
Open it in Excel and work down it by hand if you would rather not wait.

---

## Settings

| Setting | Default | What it does |
|---|---|---|
| `SPONSORSHIP_MAX_LEADS` | 40 | Targets per run |
| `SPONSORSHIP_MIN_SCORE` | 0.30 | How promising before drafting |
| `SPONSOR_FILE` | `profiles/sponsors.yaml` | Your target list |
| `CREATOR_PROFILE` | `profiles/creator.yaml` | Your numbers |
| `CONTACT_GUESS_ENABLED` | true | Allow pattern addresses when nothing is published |
| `CRAWL_BROWSER_UA` | true | Identify as a browser so commercial sites load |
| `DAILY_SEND_CAP` | 40 | Hard ceiling on emails per day |
| `DRY_RUN` | true | Nothing leaves the machine until you set this to false |
| `DISCOVER_ENABLED` | true | Let it go out to the web at all |
| `DISCOVER_INTERVAL_SECONDS` | 604800 | How often a sweep is due - weekly |
| `PROSPECT_MAX_CHECK` | 40 | Candidates read per sweep |
| `PROSPECT_MAX_PROPOSE` | 15 | How many reach an approval card |
| `PROSPECT_INDIA_MIN` | 0.30 | How Indian a site must look |
| `YOUTUBE_MINE_PAUSE` | 2.0 | Gap between video pages, to avoid rate limits |

---

## Before you send for real

`DRY_RUN=true` prints instead of sending. Leave it on until:

- You have read five or six drafts end to end and they sound like you
- SPF, DKIM and DMARC are set up on the sending address, or a slow drip lands
  in spam and burns it
- You have decided whether you are happy to do barter deals (you are, per
  `accepts_barter` in creator.yaml — change it if that stops being true)

Then set `DRY_RUN=false`. The daily cap and the approval gate still apply.

One thing worth doing by hand before any of this: sign up to EarnKaro and
Cuelinks, and join Amazon Associates India. That takes an afternoon, needs no
one's permission, and starts earning on the next video.

---

## Honest limits on the finding half

**YouTube rate-limits hard**, and more so from a datacentre than from a home
connection. A sweep that gets throttled returns what it managed rather than
failing. `YOUTUBE_MINE_PAUSE` controls the pace.

**The open search engines block datacentre addresses.** I could not verify them
from my sandbox - every one either challenged or refused. They should work from
your machine; if they do not, a free Brave or Serper key in `SEARCH_PROVIDER`
makes that source certain. The other four sources are unaffected and were all
verified live.

**Guessing a domain from a headline is not perfect.** The site still has to
read as that brand and as Indian before it is kept, and you still see it before
it is added - but expect the occasional odd one. Rejecting it is not wasted:
that is how the brain learns.
