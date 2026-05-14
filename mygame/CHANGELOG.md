# Re:Void Changelog

All notable changes to Re:Void are documented here.
Format: `[V.XX] — Description` per release, newest at the top.

---

## [V.01] — Initial Release

### In-Game Systems
- **Wisp system** — OOC presence layer; players arrive as Wisps before stepping into a character
- **Character creation** (`chargen`) — name, pronouns, species, age, description, bio
- **Zone & wardrobe system** — body zones with freeform clothing, outfit saving
- **Consent system** — content flags, per-player grants, safeword/yellow commands
- **O'gram system** — in-game offline messaging via EvMenu wizard; tiefling triplet couriers (Seraphine, Calix, Vesper) with randomized arrival lines; four message types (letter, affection, invitation, realm invite); delivered on next login
- **Wisp ambient scripts** — mood-reactive ambient messages in rooms
- **In-game text editor** — multi-line editor used by setdesc, setbio, ogram, and zone set

### Website
- Full site redesign — dark purple aesthetic, Cinzel Decorative / Cormorant Garamond typography, animated liquid drip header, scrolling ticker
- **Homepage** — hero section, news widget, status widget, sidebar
- **News app** — staff-managed news posts displayed on homepage
- **O'gram mailbox** — web-based inbox, outbox, compose, and message detail pages
- **Staff contact page** — open contact form routing to superuser inbox
- **Forum** — five boards (Announcements, General OOC, Lore & Worldbuilding, Character Boards, Bug Reports & Requests); thread creation, replies, edit/delete, staff pin/lock
- **New Player Guide** — tabbed guide covering connecting, first login, commands, zones, consent, ograms, and the text editor
- **Domain** — revoid.nexus live with SSL (Let's Encrypt), Nginx reverse proxy, webclient websocket working

### Infrastructure
- Evennia on DigitalOcean droplet
- Nginx configured as reverse proxy (HTTP → port 4001, WebSocket → port 4002)
- Certbot SSL certificate for revoid.nexus and www.revoid.nexus
- UFW firewall: ports 22, 80, 443, 4000, 4001 open

---

## [V.02] — In Progress

### Added
- **Shard economy** — currency system with passive income (1–7/10 min solo, 5–20 with others), 1,000/day cap, and daily 15-shard allowance O'gram from The Witch delivered by a random triplet courier
- **Wallet command** — `wallet` / `shards` shows balance and last 8 transactions
- **Pay / tip commands** — `pay <char> = <amount>` and `tip <char> = <amount>` for player-to-player transfers
- **ShardTransaction log** — every shard movement recorded in Django admin
- **Triplet allowance delivery** — Seraphine and Calix have a 50% chance of a wandering hand; Vesper is always shy and flustered
- `GLOBAL_SCRIPTS` wired up for PassiveIncomeScript and DailyAllowanceScript

- **Zone wardrobe web editor** — edit zone nude descs, visibility, zone type, consent flags, and intimate toggle from the website; freeform items per zone shown with lock status, key holder, and owner-editable player_desc
- **Freeform item overhaul** — `place` always appends (never replaces nude desc); `place/in` for orifice placement; `place/cover` for clothing-layer items (chastity belts, gags, blindfolds); `edititem` command lets owners rewrite any item's desc even if plock'd
- **Rendering model** — nude desc is permanent base; clothing (`wear`), cover-mode items, on-items, and in-items all append in that order with ` — ` separator
- **Consent system additions** — `allow_jump` and `allow_summon` added as Privacy flags; visible in `consent` display as a third section; per-player overrides supported
- **Housing system** — `HousingRoom` typeclass with owner, friend list, builder list, and lock flag; `web/housing` Django app with `HousingPlot` allocation model; `home`, `sethome`, `grid`, and `housing` commands; `housing dig` creates new rooms (spends a plot slot) with bidirectional exits; `housing exit` renames exits; friend/builder list management
- **Teleport commands** — `jump` (to character or room by name/#dbref, checks consent + room protection); `summon` (sends accept/decline prompt, 60-second timeout); `accept` / `decline`; housing owner/friends bypass jump protection on their own rooms
- **Durgin Ironwood NPC** — scripted housing vendor with full dialogue, personality, inappropriate commentary, and randomised purchase responses; `world/durgin_spawn.py` for one-time placement; priced tent and room pack purchases integrated with shard economy and HousingPlot ledger

### Design Notes Added
- `design/furniture_system.md` — full spec for the planned furniture token system (desc injection like zone tokens, carryable items, room placement, catalogue, tech/magical item scripting pattern, future vendor hooks)

### Planned
- **Furniture system** — see `design/furniture_system.md`; purchasable items from Durgin (anchor points, spanking benches, bondage frames, atmospheric items, magical/tech items); desc injection into room appearance; `housing furnish/pickup/describe` commands
- Durgin's physical shop room — placeholder pending grid room build; prose and set-dressing written, waiting for a room to live in
- Builder tools & QOL improvements
- O'gram system improvements (message length limits, postal office integration)
- Site styling pass (login, register, character pages)
- Additional features TBD

---
