# **F1 Analysis Hub**

**F1 Analysis Hub** is a fully-featured Formula 1 statistics and news platform that combines real-time API-powered race data, custom analytics, personalized user features, and curated news aggregation into one cohesive application. Built with Django, Bootstrap 5, and a carefully structured set of backend services, this project aims to give F1 fans a fast, intuitive, data-rich experience that goes far beyond simple standings pages or static season summaries.

Unlike general-purpose sites, this hub brings together **live driver and constructor statistics**, **detailed race breakdowns**, **sprint and GP analytics**, **favorite tracking**, and **automatic Google News integration** — all in a smooth dark-theme interface that works equally well across desktop and mobile. It was built by a longtime F1 fan who wanted to understand the sport in deeper, more dynamic ways.

---

# **Distinctiveness and Complexity**

F1 Analysis Hub is distinct from any prior CS50W project in both purpose and architecture. None of the course’s earlier assignments involve live data from third-party APIs, detailed computation of sports analytics, dynamic personalized news aggregation, or multi-layered context-driven UI features. While Projects 2 and 4 involve user accounts and interactions, their domains (e-commerce and social networking) do not overlap at all with what this platform attempts to achieve. This project is neither a marketplace nor a social network; instead, it is a **sports analytics dashboard**, deeply integrated with real-world data sources and personalized content.

One major component of the project’s complexity is its **heavy reliance on external APIs**, specifically the Jolpica F1 API (a successor to Ergast). The project includes a custom-built `JolpiClient` responsible for all HTTP requests, complete with structured URL builders, fallback logic, caching, rate-limiting considerations, and graceful error reporting. This alone goes substantially beyond the scope of any previous CS50W assignment, none of which requires students to engineer their own live data client.

Another core element of complexity arises from the **analytics layer**, where the app calculates derivative statistics such as:

* mechanical-only DNFs,
* sprint vs GP-specific aggregates,
* last-five GP performance trends,
* constructor-wide aggregation across multiple drivers,
* and filtering race results based on future/past date logic.

These analytics are not provided directly by the API; they are computed through application logic that manipulates incoming JSON structures. This analytical component makes the project truly unique and demonstrates complexity far beyond simple CRUD operations.

Finally, the personalization system — consisting of favorite drivers and constructors, user-specific dashboards, and curated news fetched dynamically from Google News — adds another architectural layer. Each user sees **their own tailored news feed** based on who they follow, in addition to a global F1 news section. This merges RSS parsing, caching, error recovery, and cross-referenced template rendering into a cohesive experience that is simply not present in any course-provided project.

Together, these dimensions (API engineering, analytics computation, personalized news aggregation, and dynamic performance caching) create a project that is both distinct and substantially more complex than any prior assignment.

---

# **Project Features**

### **Live F1 Stats & Detail Pages**

* Driver detail pages with full GP and Sprint analytics
* Standing position, points, podium counts, poles, DNFs* (mechanical only), top 10 finishes
* Last five completed GPs with position, timing, and status
* Constructor pages with aggregated performance metrics and livery display
* Automatic filtering of completed races (future rounds hidden)

### **Favorites System**

* Users may favorite both drivers and constructors
* Dedicated “My Hub” page showing all selected favorites
* Per-favorite curated article section

### **News Integration**

* Google News RSS parsing
* Automatic retrieval of:

  * Driver-specific news
  * Constructor-specific news
  * Global F1 headlines
* Server-side caching for fast performance
* Configurable provider indicator

### **API Health Monitoring**

* Background request checks via context processor
* Dynamic navbar alerts if API is slow, degraded, or unreachable

### **Navigation Enhancements**

* AJAX-powered lazy-loaded dropdowns for drivers and teams
* Filtering inputs for quick search
* Thumbnails, flags, team icons

### **Authentication**

* Custom signup form
* User login/logout
* Access-controlled “My Hub” page

### **Mobile Responsive**

* Bootstrap 5 layout
* Tested at various screen widths for clean adaptability

---

# **Project Structure / File Overview**

```
project root/
│   README.md
│   manage.py
│   requirements.txt
│
├── f1/
│   ├── views.py              # All view logic, analytics, detail pages, hub, auth
│   ├── models.py             # FavoriteDriver and FavoriteConstructor models
│   ├── forms.py              # SignUpForm
│   ├── services.py           # JolpiClient, URL builders, API helpers
│   ├── news.py               # Google News RSS fetching, parsing, caching
│   ├── context_processors.py # API health checker + JSON banners
│   ├── urls.py               # Main routing
│   ├── templates/f1/         # All HTML templates (drivers, constructors, hub, auth)
│   └── static/f1/            # CSS, images (drivers, flags, livery, logos)
│
└── f1capstone/
    └── settings.py           # Project configuration
```

---

# **How to Run F1 Analysis Hub**

1. **Clone the repo:**

   ```
   git clone <your-repo-url>
   cd f1capstone
   ```

2. **Create a virtual environment:**

   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```
   pip install -r requirements.txt
   ```

4. **Run migrations:**

   ```
   python manage.py migrate
   ```

5. **Start the server:**

   ```
   python manage.py runserver
   ```

6. Visit:
   **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

# **Additional Notes**

* This project uses **cached external API calls**; if Jolpica is temporarily slow or unavailable, the app will show a warning banner but continue running gracefully.
* The news feature requires internet access (RSS fetch).
* No API keys are required.
* All thumbnails and livery images are local assets included in `/static/f1/img/`.

---

# **Conclusion**

F1 Analysis Hub blends multiple disciplines — web development, data engineering, caching, API parsing, UI design, and sports analytics — into an ambitious and enjoyable project. It is the kind of application I always wished to create as an F1 fan, and building it provided both technical depth and personal satisfaction. I hope you enjoy exploring it as much as I enjoyed creating it.

---
