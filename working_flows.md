# Vibe Check — Complete Working Flow Document

> This document traces every user action through the **three layers** of the application:
> **Frontend (HTML/JS)** → **Backend API (Django REST)** → **Database (PostgreSQL)**

---

## SYSTEM ARCHITECTURE

```mermaid
graph TB
    subgraph Frontend["Frontend (Browser - Vanilla JS + Tailwind)"]
        LOGIN[login.html]
        HOME[index.html]
        DETAIL[event.html]
        TICKETS[tickets.html]
        ORGANIZER[organizer.html]
        SCANNER[scanner.html]
        APIJS[api.js - Shared Client]
    end

    subgraph Backend["Backend (Django REST Framework)"]
        AUTH_V[Auth Views]
        EVENT_V[Event Views]
        TICKET_V[Ticket Views]
        SERIAL[Serializers]
        PERMS[Permissions]
        FILTERS[Filters]
    end

    subgraph Database["PostgreSQL Database"]
        USERS[(accounts_customuser)]
        EVENTS[(events_event)]
        TICKETS_DB[(events_ticket)]
    end

    APIJS -->|HTTP + JWT| AUTH_V
    APIJS -->|HTTP + JWT| EVENT_V
    APIJS -->|HTTP + JWT| TICKET_V

    AUTH_V --> USERS
    EVENT_V --> EVENTS
    TICKET_V --> TICKETS_DB
    TICKETS_DB -->|FK| USERS
    TICKETS_DB -->|FK| EVENTS
    EVENTS -->|FK| USERS
```

---

## FLOW 1: USER REGISTRATION & LOGIN

### What the user does
Opens `login.html` → types username & password → clicks "Sign In"

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant U as User Browser
    participant JS as api.js
    participant API as Django API
    participant DB as PostgreSQL

    U->>JS: Click "Sign In" (username: admin, password: admin123)
    JS->>API: POST /api/auth/token/<br/>{"username":"admin","password":"admin123"}
    API->>DB: SELECT * FROM accounts_customuser<br/>WHERE username='admin'
    DB-->>API: Row found, password hash matches
    API-->>JS: 200 {"access":"eyJ...", "refresh":"eyJ..."}
    JS->>JS: localStorage.setItem('vibe_token', access)<br/>localStorage.setItem('vibe_refresh', refresh)
    JS->>API: GET /api/auth/profile/<br/>Authorization: Bearer eyJ...
    API->>DB: SELECT id, username, email, role, avatar, bio<br/>FROM accounts_customuser WHERE id=1
    DB-->>API: User row returned
    API-->>JS: 200 {"id":1,"username":"admin","role":"organizer",...}
    JS->>JS: localStorage.setItem('vibe_user', JSON.stringify(profile))
    JS->>U: Redirect to index.html
```

### What gets stored

| Layer | Where | What |
|---|---|---|
| Browser localStorage | `vibe_token` | JWT access token (expires 2 hours) |
| Browser localStorage | `vibe_refresh` | JWT refresh token (expires 7 days) |
| Browser localStorage | `vibe_user` | `{"id":1,"username":"admin","role":"organizer",...}` |
| Database | No change | Login does not write to DB — read-only verification |

### Token refresh (automatic, invisible to user)

When any API call returns `401`:
1. `api.js` calls `POST /api/auth/token/refresh/` with the stored refresh token
2. Backend validates refresh token → returns new access token
3. `api.js` stores new access token → retries the original request
4. User never sees a login screen (unless refresh token also expired)

---

## FLOW 2: BROWSING & DISCOVERING EVENTS

### What the user does
Opens `index.html` → sees event cards → clicks category pill "TECH" → types "Mumbai" in search

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant U as User Browser
    participant JS as index.html + api.js
    participant API as EventListCreateView
    participant DB as PostgreSQL

    Note over U,DB: Page Load
    JS->>API: GET /api/events/
    API->>DB: SELECT e.*, u.username, u.avatar<br/>FROM events_event e<br/>JOIN accounts_customuser u ON e.organizer_id=u.id<br/>WHERE e.is_published=TRUE<br/>ORDER BY e.date ASC<br/>LIMIT 20
    DB-->>API: 2 event rows returned
    API->>API: Serialize: compute tickets_remaining<br/>(SELECT COUNT(*) FROM events_ticket WHERE event_id=e.id)<br/>→ remaining = total_tickets - count
    API-->>JS: 200 {"count":2, "results":[{event1},{event2}]}
    JS->>U: Render event cards with images, prices, venue

    Note over U,DB: User clicks "TECH" filter
    JS->>API: GET /api/events/?category=tech
    API->>DB: Same query + WHERE e.category='tech'
    DB-->>API: Filtered rows
    API-->>JS: 200 {"count":1, "results":[{tech event}]}
    JS->>U: Re-render grid with filtered cards

    Note over U,DB: User types "Mumbai" in search
    JS->>JS: Debounce 450ms
    JS->>API: GET /api/events/?category=tech&search=Mumbai
    API->>DB: Same query + WHERE (e.title ILIKE '%Mumbai%'<br/>OR e.description ILIKE '%Mumbai%'<br/>OR e.venue_name ILIKE '%Mumbai%')
    DB-->>API: Matching rows
    API-->>JS: Filtered results
    JS->>U: Update grid
```

### What gets returned per event

```json
{
  "id": 1,
  "title": "Tech Meetup Mumbai",
  "category": "tech",
  "category_display": "Tech",         // ← Python: get_category_display()
  "date": "2026-06-15T18:00:00Z",
  "venue_name": "Bandra Kurla Complex",
  "price": "199.00",
  "image": null,
  "organizer": {
    "id": 1,
    "username": "admin",
    "first_name": "",
    "last_name": "",
    "avatar": null
  },
  "tickets_remaining": 49,            // ← Python: total_tickets - tickets.count()
  "is_upcoming": true,                // ← Python: date > timezone.now()
  "is_published": true
}
```

---

## FLOW 3: BUYING A TICKET

### What the user does
On `event.html` → clicks "GET TICKET" → sees success modal → goes to My Tickets

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant U as User Browser
    participant JS as event.html + api.js
    participant API as TicketPurchaseView
    participant DB as PostgreSQL

    Note over U,DB: Load event detail
    JS->>API: GET /api/events/1/
    API->>DB: SELECT * FROM events_event WHERE id=1
    DB-->>API: Full event row + computed fields
    API-->>JS: 200 {event detail with tickets_remaining: 49}
    JS->>U: Render detail page + sticky "GET TICKET ₹199" bar

    Note over U,DB: User clicks "GET TICKET"
    U->>JS: Click buy button
    JS->>API: POST /api/tickets/purchase/<br/>Authorization: Bearer eyJ...<br/>{"event": 1}

    Note over API,DB: Validation Phase
    API->>DB: SELECT * FROM events_event WHERE id=1
    DB-->>API: Event row (is_published=true, date > now)
    API->>DB: SELECT COUNT(*) FROM events_ticket<br/>WHERE user_id=1 AND event_id=1
    DB-->>API: count=0 (no duplicate)

    Note over API,DB: Atomic Purchase (prevents overselling)
    API->>DB: BEGIN TRANSACTION
    API->>DB: SELECT * FROM events_event<br/>WHERE id=1 FOR UPDATE
    Note right of DB: Row is now LOCKED<br/>No other transaction can<br/>read this row until commit
    DB-->>API: Event row (total_tickets=50)
    API->>DB: SELECT COUNT(*) FROM events_ticket WHERE event_id=1
    DB-->>API: count=1 → remaining = 49 > 0 ✓
    API->>API: Generate ticket_hash =<br/>SHA256("1-1-uuid4()") = "870b216e..."
    API->>DB: INSERT INTO events_ticket<br/>(user_id, event_id, ticket_hash,<br/>is_scanned, price_paid)<br/>VALUES (1, 1, '870b21...', false, 199.00)
    API->>DB: COMMIT TRANSACTION
    Note right of DB: Row lock released

    DB-->>API: New ticket row (id=2)
    API-->>JS: 201 {"id":2, "ticket_hash":"870b21...",<br/>"is_scanned":false, "price_paid":"199.00", ...}
    JS->>U: Show green success modal<br/>"Ticket Confirmed! 🎉"
```

### What gets written to database

**`events_ticket` — new row inserted:**

| Column | Value | Source |
|---|---|---|
| `id` | 2 | Auto-increment |
| `user_id` | 1 | From JWT token (`request.user`) |
| `event_id` | 1 | From request body `{"event": 1}` |
| `ticket_hash` | `870b216e5e53...` | SHA-256 of `"1-1-<uuid4>"` |
| `is_scanned` | `false` | Default |
| `scanned_at` | `NULL` | Not scanned yet |
| `purchased_at` | `2026-05-06 08:17:16 UTC` | Auto `now()` |
| `price_paid` | `199.00` | Snapshot of `event.price` at purchase time |

### Why `select_for_update()` matters

Without it, if 2 users buy the last ticket at the same millisecond:
```
Thread A: reads remaining = 1 ✓ → creates ticket → remaining = 0
Thread B: reads remaining = 1 ✓ → creates ticket → remaining = -1 ❌ OVERSOLD
```
With `select_for_update()`:
```
Thread A: LOCKS event row → reads remaining = 1 ✓ → creates ticket → COMMIT
Thread B: WAITS for lock → reads remaining = 0 ❌ → gets "sold out" error
```

---

## FLOW 4: VIEWING MY TICKETS + QR CODE

### What the user does
Opens `tickets.html` → sees ticket cards → taps "VIEW QR TICKET" → QR code appears

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant U as User Browser
    participant JS as tickets.html + api.js
    participant QR as qrcodejs Library
    participant API as UserTicketListView
    participant DB as PostgreSQL

    JS->>API: GET /api/user/tickets/<br/>Authorization: Bearer eyJ...
    API->>DB: SELECT t.*, e.*, u.*<br/>FROM events_ticket t<br/>JOIN events_event e ON t.event_id=e.id<br/>JOIN accounts_customuser u ON e.organizer_id=u.id<br/>WHERE t.user_id=1<br/>ORDER BY t.purchased_at DESC
    DB-->>API: Ticket rows with nested event data
    API-->>JS: 200 {"results": [{"ticket_hash":"870b21...", ...}]}

    JS->>U: Render ticket cards (event image, date, venue, status badge)
    U->>JS: Click "VIEW QR TICKET"
    JS->>QR: new QRCode(element, {text: "870b21...",<br/>colorDark: "#630ed4"})
    QR-->>JS: QR code canvas rendered
    JS->>U: Display purple QR code encoding the ticket_hash
```

### How the QR code gets its data

```
Database ticket_hash column: "870b216e5e5320bbfea51a7ff6c1cfa99d58129f5ff7bc38bc91c626b324b615"
     ↓
API returns it in JSON response as ticket.ticket_hash
     ↓
Frontend JS passes it to qrcodejs library
     ↓
Library renders it as a visual QR code on an HTML canvas
     ↓
The QR code, when scanned by any reader, outputs the same 64-char hash string
```

---

## FLOW 5: SCANNING A TICKET AT THE DOOR

### What the organizer does
Opens `scanner.html` → logs in → camera activates → points at attendee's QR → sees "Access Granted" (green) or "Already Scanned" (red)

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant O as Organizer Phone
    participant CAM as html5-qrcode Camera
    participant JS as scanner.html
    participant API as TicketVerifyView
    participant DB as PostgreSQL

    O->>JS: Login as organizer
    JS->>CAM: Start rear camera (facingMode: environment)
    CAM-->>JS: Camera stream active

    Note over O,DB: Attendee shows QR code on their phone

    CAM->>JS: onScanSuccess("870b216e5e53...")
    JS->>JS: isProcessing = true (3.5s debounce starts)
    JS->>API: POST /api/tickets/verify/<br/>Authorization: Bearer eyJ...<br/>{"ticket_hash": "870b216e5e53..."}

    Note over API,DB: Verification Chain
    API->>API: Check: request.user.is_organizer == true ✓
    API->>DB: SELECT t.*, e.*, org.*<br/>FROM events_ticket t<br/>JOIN events_event e ON t.event_id=e.id<br/>JOIN accounts_customuser org ON e.organizer_id=org.id<br/>WHERE t.ticket_hash='870b216e5e53...'
    DB-->>API: Ticket found

    API->>API: Check: ticket.event.organizer == request.user ✓
    API->>API: Check: ticket.is_scanned == false ✓

    API->>DB: UPDATE events_ticket<br/>SET is_scanned=TRUE, scanned_at=NOW()<br/>WHERE id=2
    DB-->>API: 1 row updated

    API-->>JS: 200 {"status":"access_granted", "ticket":{...}}
    JS->>O: GREEN CARD: "Access Granted ✅"<br/>Shows event name, ticket holder
    JS->>JS: cntGranted++ → update counter display

    Note over O,DB: Same QR scanned again
    CAM->>JS: onScanSuccess("870b216e5e53...")
    JS->>API: POST /api/tickets/verify/<br/>{"ticket_hash": "870b216e5e53..."}
    API->>DB: SELECT ... WHERE ticket_hash='870b21...'
    DB-->>API: is_scanned=TRUE, scanned_at='2026-05-06 08:17:16'
    API-->>JS: 409 {"status":"already_scanned",<br/>"detail":"Ticket already scanned at 2026-05-06 08:17:16 UTC"}
    JS->>O: RED CARD: "Already Scanned 🚫"<br/>Shows when it was first scanned
```

### What changes in the database

**Before scan:**

| ticket_hash | is_scanned | scanned_at |
|---|---|---|
| `870b216e5e53...` | `false` | `NULL` |

**After scan:**

| ticket_hash | is_scanned | scanned_at |
|---|---|---|
| `870b216e5e53...` | `true` | `2026-05-06 08:17:16.890507+00` |

---

## FLOW 6: ORGANIZER CREATES AN EVENT

### What the organizer does
Opens `organizer.html` → clicks "NEW EVENT" → fills form + uploads banner image → clicks "Create Event"

### Step-by-step data journey

```mermaid
sequenceDiagram
    participant O as Organizer Browser
    participant JS as organizer.html + api.js
    participant API as EventListCreateView
    participant FS as Server Filesystem
    participant DB as PostgreSQL

    O->>JS: Fill form: title, description, category,<br/>date, venue, price, tickets, image file
    O->>JS: Check "Publish immediately"
    O->>JS: Click "Create Event"

    JS->>JS: Build FormData object<br/>(supports binary image upload)
    JS->>API: POST /api/events/<br/>Content-Type: multipart/form-data<br/>Authorization: Bearer eyJ...<br/>[title, description, ..., image binary]

    API->>API: IsOrganizerOrReadOnly: user.is_organizer == true ✓
    API->>API: Validate: price >= 0, total_tickets >= 1

    API->>FS: Save image to /media/events/images/<filename>
    FS-->>API: File path: "events/images/banner_abc.jpg"

    API->>DB: INSERT INTO events_event<br/>(title, description, category, date,<br/>venue_name, price, total_tickets,<br/>image, organizer_id, is_published)<br/>VALUES ('Tech Summit', '...', 'tech',<br/>'2026-12-01 18:00', 'BKC', 199.00,<br/>50, 'events/images/banner_abc.jpg',<br/>1, true)
    DB-->>API: New event row (id=3)

    API->>DB: SELECT (for serialization with computed fields)
    API-->>JS: 201 {full event detail with tickets_remaining: 50}
    JS->>JS: closeModal() → loadEvents() refreshes list
    JS->>O: New event appears in dashboard list<br/>status: "LIVE", sold: 0/50, revenue: ₹0
```

### What gets written to database

**`events_event` — new row:**

| Column | Value |
|---|---|
| `id` | 3 |
| `title` | "Tech Summit" |
| `description` | "Join us for..." |
| `category` | "tech" |
| `date` | `2026-12-01 18:00:00+00` |
| `venue_name` | "BKC" |
| `price` | `199.00` |
| `total_tickets` | 50 |
| `image` | `events/images/banner_abc.jpg` |
| `organizer_id` | 1 (from JWT) |
| `is_published` | `true` |
| `created_at` | auto |
| `updated_at` | auto |

---

## FLOW 7: ORGANIZER EDITS & DELETES EVENT

### Edit flow

```mermaid
sequenceDiagram
    participant O as Organizer
    participant JS as organizer.html
    participant API as EventDetailView
    participant DB as PostgreSQL

    O->>JS: Click "Edit" on event card
    JS->>JS: Pre-fill modal form with existing event data
    O->>JS: Change title + toggle publish off
    O->>JS: Click "Save Changes"
    JS->>API: PATCH /api/events/3/<br/>FormData: {title: "New Title", is_published: false}
    API->>API: IsEventOwnerOrReadOnly:<br/>event.organizer_id == request.user.id ✓
    API->>DB: UPDATE events_event<br/>SET title='New Title', is_published=FALSE,<br/>updated_at=NOW()<br/>WHERE id=3
    DB-->>API: Updated row
    API-->>JS: 200 {updated event}
    JS->>O: Dashboard refreshes, event now shows "DRAFT" badge
```

### Delete flow

```mermaid
sequenceDiagram
    participant O as Organizer
    participant JS as organizer.html
    participant API as EventDetailView
    participant DB as PostgreSQL

    O->>JS: Click "Delete" on event card
    JS->>O: Confirmation modal:<br/>"Delete 'Tech Summit'?"<br/>"⚠️ 5 tickets already sold!"
    O->>JS: Click "Delete" to confirm
    JS->>API: DELETE /api/events/3/<br/>Authorization: Bearer eyJ...
    API->>API: IsEventOwnerOrReadOnly: owner check ✓
    API->>DB: DELETE FROM events_ticket WHERE event_id=3
    Note right of DB: CASCADE: tickets deleted first
    API->>DB: DELETE FROM events_event WHERE id=3
    DB-->>API: Row deleted
    API-->>JS: 204 No Content
    JS->>O: Event removed from dashboard list<br/>Stats recalculated
```

---

## COMPLETE DATA RELATIONSHIP MAP

```mermaid
erDiagram
    CUSTOMUSER {
        int id PK
        string username UK
        string email UK
        string password
        string role "regular | organizer"
        string avatar "nullable"
        string bio
        datetime date_joined
    }

    EVENT {
        int id PK
        string title
        text description
        string category "music | tech | food | arts"
        datetime date
        string venue_name
        decimal price
        int total_tickets
        string image "nullable"
        bool is_published
        int organizer_id FK
        datetime created_at
        datetime updated_at
    }

    TICKET {
        int id PK
        int user_id FK
        int event_id FK
        string ticket_hash UK "SHA-256, 64 chars"
        bool is_scanned "default false"
        datetime scanned_at "nullable"
        datetime purchased_at
        decimal price_paid
    }

    CUSTOMUSER ||--o{ EVENT : "organizes"
    CUSTOMUSER ||--o{ TICKET : "purchases"
    EVENT ||--o{ TICKET : "has tickets"
```

---

## FRONTEND → API → DATABASE MAPPING

| Frontend Page | User Action | API Call | Database Effect |
|---|---|---|---|
| `login.html` | Click "Sign In" | `POST /api/auth/token/` | READ `accounts_customuser` |
| `index.html` | Page loads | `GET /api/events/` | READ `events_event` + JOIN user |
| `index.html` | Click category pill | `GET /api/events/?category=tech` | READ with WHERE filter |
| `index.html` | Type in search | `GET /api/events/?search=mumbai` | READ with ILIKE search |
| `event.html` | Page loads | `GET /api/events/1/` | READ single event + ticket count |
| `event.html` | Click "Get Ticket" | `POST /api/tickets/purchase/` | INSERT `events_ticket` (with row lock) |
| `tickets.html` | Page loads | `GET /api/user/tickets/` | READ `events_ticket` WHERE user_id=me |
| `tickets.html` | Tap "VIEW QR" | No API call | QR rendered client-side from stored hash |
| `scanner.html` | Camera reads QR | `POST /api/tickets/verify/` | UPDATE `events_ticket` SET is_scanned=TRUE |
| `organizer.html` | Page loads | `GET /api/organizer/events/` | READ events WHERE organizer_id=me |
| `organizer.html` | Click "New Event" | `POST /api/events/` | INSERT `events_event` |
| `organizer.html` | Click "Edit" | `PATCH /api/events/3/` | UPDATE `events_event` |
| `organizer.html` | Click "Delete" | `DELETE /api/events/3/` | DELETE `events_event` + CASCADE tickets |
