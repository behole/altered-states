# Slot Machine Project Wheel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone interactive slot machine page at `site/wheel/index.html` that spins through a configurable list of projects and reveals the winner in a modal.

**Architecture:** Single HTML file with embedded CSS and JS (no build step). Projects loaded from `projects.json` with an inline JSON fallback. Spin physics driven by a `requestAnimationFrame` loop with ramp-up, cruise, and spring-damped deceleration phases.

**Tech Stack:** Vanilla HTML5, CSS3, ES2020 JavaScript. No frameworks, no dependencies.

---

## File Structure

```
site/
├── index.html              (existing — add nav link)
└── wheel/
    ├── index.html          (new — complete slot machine page)
    └── projects.json       (new — configurable project list)
```

---

## Task 1: Create `site/wheel/projects.json`

**Files:**
- Create: `site/wheel/projects.json`

- [ ] **Step 1: Create the directory and file**

```bash
mkdir -p site/wheel
```

Create `site/wheel/projects.json`:

```json
[
  {
    "id": "altered-states",
    "name": "Altered States",
    "description": "AI skills that simulate the phenomenology of mind-altering substances, grounded in peer-reviewed clinical research.",
    "url": "https://github.com/jjoosshhmbpm1/altered-states",
    "color": "#e74c3c"
  },
  {
    "id": "temporal-lab",
    "name": "Temporal Lab",
    "description": "Autonomous character systems with persistent memory, emotional arcs, and temporal reasoning.",
    "url": "https://example.com/temporal-lab",
    "color": "#3498db"
  },
  {
    "id": "music-experiments",
    "name": "Music Experiments",
    "description": "10-persona audio generation: describe a song and hear it through the lens of different altered states.",
    "url": "https://example.com/music-experiments",
    "color": "#9b59b6"
  },
  {
    "id": "visual-fingerprints",
    "name": "Visual Fingerprints",
    "description": "Generative art explorations of perceptual changes across different phenomenological states.",
    "url": "https://example.com/visual-fingerprints",
    "color": "#2ecc71"
  },
  {
    "id": "eval-framework",
    "name": "Evaluation Framework",
    "description": "Cross-model testing protocols, blind evaluations, and structured reporting for altered-state skill quality.",
    "url": "https://example.com/eval-framework",
    "color": "#f39c12"
  }
]
```

- [ ] **Step 2: Validate JSON**

Run:
```bash
python3 -m json.tool site/wheel/projects.json > /dev/null && echo "Valid JSON"
```

Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add site/wheel/projects.json
git commit -m "feat(wheel): add configurable projects.json"
```

---

## Task 2: Create `site/wheel/index.html`

**Files:**
- Create: `site/wheel/index.html`

- [ ] **Step 1: Write the complete page**

Create `site/wheel/index.html` with the following content. This is the full implementation — HTML structure, CSS, and JavaScript in one file.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Project Wheel</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: #111;
      color: #fff;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .page {
      width: 100%;
      max-width: 480px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 24px;
    }

    h1 {
      font-size: 28px;
      font-weight: 600;
      text-align: center;
    }

    .slot-container {
      width: 100%;
      height: 160px;
      position: relative;
      overflow: hidden;
      border: 2px solid #e74c3c;
      border-radius: 12px;
      background: #1a1a1a;
      cursor: pointer;
    }

    .slot-container::before,
    .slot-container::after {
      content: '';
      position: absolute;
      left: 0;
      right: 0;
      height: 40px;
      pointer-events: none;
      z-index: 2;
    }

    .slot-container::before {
      top: 0;
      background: linear-gradient(to bottom, #1a1a1a, transparent);
    }

    .slot-container::after {
      bottom: 0;
      background: linear-gradient(to top, #1a1a1a, transparent);
    }

    .winner-indicator {
      position: absolute;
      top: 50%;
      left: 0;
      right: 0;
      height: 2px;
      background: #e74c3c;
      transform: translateY(-50%);
      z-index: 1;
      opacity: 0.5;
    }

    .strip {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      will-change: transform;
    }

    .card {
      height: 140px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #333;
      border-radius: 8px;
      background: #222;
      font-size: 18px;
      font-weight: 500;
      padding: 0 16px;
      text-align: center;
    }

    .card:last-child {
      margin-bottom: 0;
    }

    .spin-button {
      padding: 14px 48px;
      font-size: 18px;
      font-weight: 600;
      border: none;
      border-radius: 8px;
      background: #e74c3c;
      color: #fff;
      cursor: pointer;
      transition: opacity 0.2s, transform 0.1s;
    }

    .spin-button:hover:not(:disabled) {
      opacity: 0.9;
      transform: scale(1.02);
    }

    .spin-button:active:not(:disabled) {
      transform: scale(0.98);
    }

    .spin-button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .error-message {
      color: #e74c3c;
      text-align: center;
      font-size: 14px;
    }

    .retry-button {
      margin-top: 8px;
      padding: 8px 16px;
      font-size: 14px;
      border: 1px solid #e74c3c;
      border-radius: 6px;
      background: transparent;
      color: #e74c3c;
      cursor: pointer;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.2s, visibility 0.2s;
      z-index: 100;
    }

    .modal-backdrop.active {
      opacity: 1;
      visibility: visible;
    }

    .modal {
      background: #1a1a1a;
      border: 1px solid #333;
      border-radius: 16px;
      padding: 32px;
      width: 100%;
      max-width: 400px;
      transform: scale(0.95);
      transition: transform 0.2s;
    }

    .modal-backdrop.active .modal {
      transform: scale(1);
    }

    @media (max-width: 480px) {
      .modal {
        transform: translateY(20px);
      }
      .modal-backdrop.active .modal {
        transform: translateY(0);
      }
    }

    .modal h2 {
      font-size: 24px;
      margin-bottom: 12px;
    }

    .modal p {
      color: #aaa;
      line-height: 1.5;
      margin-bottom: 24px;
    }

    .modal-actions {
      display: flex;
      gap: 12px;
    }

    .btn-primary,
    .btn-secondary {
      flex: 1;
      padding: 12px 20px;
      font-size: 16px;
      font-weight: 500;
      border-radius: 8px;
      text-align: center;
      text-decoration: none;
      cursor: pointer;
      transition: opacity 0.2s;
      border: none;
    }

    .btn-primary:hover,
    .btn-secondary:hover {
      opacity: 0.9;
    }

    .btn-primary {
      background: #e74c3c;
      color: #fff;
    }

    .btn-secondary {
      background: transparent;
      color: #fff;
      border: 1px solid #555;
    }

    @media (prefers-reduced-motion: reduce) {
      .strip {
        transition: none !important;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>Pick a Project</h1>

    <div class="slot-container" id="slotContainer">
      <div class="strip" id="strip"></div>
      <div class="winner-indicator"></div>
    </div>

    <button class="spin-button" id="spinButton" aria-label="Spin the wheel">SPIN</button>

    <div class="error-message" id="errorMessage">
      <span id="errorText"></span>
      <button class="retry-button" id="retryButton" style="display:none;">Retry</button>
    </div>
  </div>

  <div class="modal-backdrop" id="modalBackdrop" role="dialog" aria-modal="true" aria-label="Project selected">
    <div class="modal">
      <h2 id="modalTitle"></h2>
      <p id="modalDescription"></p>
      <div class="modal-actions">
        <a id="modalLink" href="#" target="_blank" class="btn-primary">Visit Project</a>
        <button id="spinAgainButton" class="btn-secondary">Spin Again</button>
      </div>
    </div>
  </div>

  <script type="application/json" id="projects-data">
  [
    {"id":"example-1","name":"Example Project 1","description":"This is a sample project description.","url":"https://example.com"},
    {"id":"example-2","name":"Example Project 2","description":"Another sample project.","url":"https://example.com"},
    {"id":"example-3","name":"Example Project 3","description":"A third sample project.","url":"https://example.com"}
  ]
  </script>

  <script>
    const CARD_HEIGHT = 140;
    const CARD_GAP = 16;
    const CARD_SPACING = CARD_HEIGHT + CARD_GAP;
    const VIEWPORT_HEIGHT = 160;
    const CENTER_OFFSET = (VIEWPORT_HEIGHT - CARD_HEIGHT) / 2;
    const DUPLICATES = 3;
    const RAMP_UP_MS = 200;
    const MAX_SPEED = 2500;
    const SPRING_STIFFNESS = 8;
    const SPRING_DAMPING = 0.85;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let projects = [];
    let isSpinning = false;
    let animationId = null;
    let stripPosition = CENTER_OFFSET;

    const strip = document.getElementById('strip');
    const spinButton = document.getElementById('spinButton');
    const slotContainer = document.getElementById('slotContainer');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const modalTitle = document.getElementById('modalTitle');
    const modalDescription = document.getElementById('modalDescription');
    const modalLink = document.getElementById('modalLink');
    const spinAgainButton = document.getElementById('spinAgainButton');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    const retryButton = document.getElementById('retryButton');

    async function loadProjects() {
      errorText.textContent = '';
      retryButton.style.display = 'none';
      spinButton.disabled = false;

      try {
        const response = await fetch('projects.json');
        if (!response.ok) throw new Error('Failed to load');
        projects = await response.json();
        validateAndRender();
      } catch (e) {
        const fallback = document.getElementById('projects-data');
        if (fallback) {
          try {
            projects = JSON.parse(fallback.textContent);
            validateAndRender();
            return;
          } catch {}
        }
        showError("Couldn't load projects. Check that projects.json exists.");
      }
    }

    function validateAndRender() {
      if (!Array.isArray(projects) || projects.length === 0) {
        showError('Add projects to spin!');
        return;
      }
      renderStrip();
    }

    function showError(msg) {
      errorText.textContent = msg;
      retryButton.style.display = 'inline-block';
      spinButton.disabled = true;
    }

    function renderStrip() {
      strip.innerHTML = '';
      const totalCards = projects.length * DUPLICATES;

      for (let i = 0; i < totalCards; i++) {
        const project = projects[i % projects.length];
        const card = document.createElement('div');
        card.className = 'card';
        card.textContent = project.name;
        card.dataset.projectId = project.id;
        strip.appendChild(card);
      }

      stripPosition = CENTER_OFFSET;
      strip.style.transform = `translateY(${stripPosition}px)`;
    }

    function startSpin() {
      if (isSpinning || projects.length === 0) return;
      isSpinning = true;
      spinButton.disabled = true;
      closeModal();

      const winnerIndex = Math.floor(Math.random() * projects.length);
      const winner = projects[winnerIndex];

      if (prefersReducedMotion) {
        const middleBase = projects.length;
        const targetIndex = middleBase + winnerIndex;
        stripPosition = CENTER_OFFSET - (targetIndex * CARD_SPACING);
        strip.style.transform = `translateY(${stripPosition}px)`;
        isSpinning = false;
        spinButton.disabled = false;
        showWinModal(winner);
        return;
      }

      const middleBase = projects.length;
      const targetIndex = middleBase + winnerIndex;
      const targetPosition = CENTER_OFFSET - (targetIndex * CARD_SPACING);

      const state = {
        position: stripPosition,
        velocity: 0,
        target: targetPosition,
        startTime: performance.now(),
        phase: 'ramp-up',
        winner
      };

      let lastTime = performance.now();

      function animate(now) {
        const dt = Math.min((now - lastTime) / 1000, 0.05);
        lastTime = now;
        const elapsed = now - state.startTime;

        if (state.phase === 'ramp-up') {
          const progress = Math.min(elapsed / RAMP_UP_MS, 1);
          state.velocity = MAX_SPEED * progress;
          if (progress >= 1) state.phase = 'cruise';
        } else if (state.phase === 'cruise') {
          state.velocity = MAX_SPEED;
          const distance = Math.abs(state.target - state.position);
          const decelDistance = MAX_SPEED * 0.5;
          if (distance <= decelDistance) {
            state.phase = 'decelerate';
          }
        } else if (state.phase === 'decelerate') {
          const force = (state.target - state.position) * SPRING_STIFFNESS;
          state.velocity = state.velocity * SPRING_DAMPING + force * dt;

          if (Math.abs(state.target - state.position) < 0.5 && Math.abs(state.velocity) < 5) {
            state.position = state.target;
            state.phase = 'done';
          }
        }

        if (state.phase !== 'done') {
          state.position += state.velocity * dt;
          strip.style.transform = `translateY(${state.position}px)`;
          animationId = requestAnimationFrame(animate);
        } else {
          stripPosition = state.position;
          isSpinning = false;
          spinButton.disabled = false;
          showWinModal(state.winner);
        }
      }

      animationId = requestAnimationFrame(animate);
    }

    function showWinModal(project) {
      modalTitle.textContent = project.name;
      if (project.description) {
        modalDescription.textContent = project.description;
        modalDescription.style.display = 'block';
      } else {
        modalDescription.style.display = 'none';
      }

      if (project.url) {
        modalLink.href = project.url;
        modalLink.style.display = 'inline-flex';
      } else {
        modalLink.style.display = 'none';
      }

      modalBackdrop.classList.add('active');
    }

    function closeModal() {
      modalBackdrop.classList.remove('active');
    }

    function resetStrip() {
      stripPosition = CENTER_OFFSET;
      strip.style.transform = `translateY(${stripPosition}px)`;
    }

    spinButton.addEventListener('click', startSpin);
    slotContainer.addEventListener('click', startSpin);

    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !e.repeat && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
        e.preventDefault();
        startSpin();
      }
    });

    spinAgainButton.addEventListener('click', () => {
      closeModal();
      resetStrip();
    });

    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) closeModal();
    });

    document.addEventListener('keydown', (e) => {
      if (e.code === 'Escape') closeModal();
    });

    retryButton.addEventListener('click', loadProjects);

    loadProjects();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify in browser — structure and data loading**

Open `site/wheel/index.html` in a browser (or serve the `site/` directory and navigate to `/wheel/`).

Check:
- Page title is "Project Wheel"
- Heading "Pick a Project" is visible
- Slot container shows 5 project cards (3 duplicates × 5 projects from `projects.json` = 15 cards, but only ~1.5 visible in viewport)
- First card is centered in the viewport
- Red winner indicator line is visible across the center
- SPIN button is visible and enabled
- No error message is shown

- [ ] **Step 3: Verify spin animation**

Click the SPIN button (or press Spacebar, or click the slot).

Check:
- Cards begin scrolling rapidly upward
- Animation has a fast start, cruises, then smoothly decelerates
- After ~2–4 seconds, the animation stops with one card perfectly centered
- The SPIN button is disabled during spin and re-enabled after
- Double-clicking/triggering during spin does nothing (no glitches)

- [ ] **Step 4: Verify win modal**

After the spin stops:

Check:
- Modal backdrop fades in
- Modal shows the winning project's name and description
- "Visit Project" button links to the project's URL (opens in new tab)
- "Spin Again" button closes the modal and resets the strip to the first project
- Pressing Escape closes the modal
- Clicking the backdrop (outside the modal) closes it

- [ ] **Step 5: Verify error handling**

Temporarily rename `site/wheel/projects.json` to something else and reload the page.

Check:
- Error message appears: "Couldn't load projects. Check that projects.json exists."
- Retry button is visible
- SPIN button is disabled
- Clicking Retry attempts to reload (will keep failing until you restore the file)

Restore the file when done:
```bash
mv site/wheel/projects.json.bak site/wheel/projects.json  # or rename back
```

- [ ] **Step 6: Verify `prefers-reduced-motion`**

Enable reduced motion in your OS settings and reload the page. Click SPIN.

Check:
- No animation plays
- The winning project is immediately shown in the center
- Modal appears instantly

Disable reduced motion when done.

- [ ] **Step 7: Commit**

```bash
git add site/wheel/index.html
git commit -m "feat(wheel): add interactive slot machine page"
```

---

## Task 3: Link from main site

**Files:**
- Modify: `site/index.html`

- [ ] **Step 1: Add a link to the wheel page**

In `site/index.html`, find the nav links section (around line 94–105, inside `<nav>`). Add a link to the wheel page:

Locate this section:
```html
    <nav class="links">
      <a href="#try">Try</a>
      <a href="#explore">Explore</a>
      <a href="#listen">Listen</a>
      <a href="#about">About</a>
    </nav>
```

Add the wheel link. Place it after "Listen" or where it makes sense in the nav flow:

```html
    <nav class="links">
      <a href="#try">Try</a>
      <a href="#explore">Explore</a>
      <a href="#listen">Listen</a>
      <a href="wheel/">Wheel</a>
      <a href="#about">About</a>
    </nav>
```

- [ ] **Step 2: Verify link works**

Open `site/index.html` in a browser, click the "Wheel" nav link.

Check:
- Navigates to `site/wheel/index.html`
- Wheel page loads correctly

- [ ] **Step 3: Commit**

```bash
git add site/index.html
git commit -m "feat(site): add nav link to project wheel"
```

---

## Spec Coverage Check

| Spec Requirement | Implementing Task |
|------------------|-------------------|
| Vertical slot machine | Task 2 — CSS and JS |
| JS `requestAnimationFrame` animation loop | Task 2 — `startSpin()` and `animate()` |
| Configurable JSON data source | Task 1 — `projects.json`; Task 2 — `loadProjects()` |
| Inline JSON fallback | Task 2 — `<script type="application/json" id="projects-data">` |
| Win modal with description + CTAs | Task 2 — `showWinModal()`, modal HTML |
| SPIN button trigger | Task 2 — `spinButton.addEventListener` |
| Click/tap on slot trigger | Task 2 — `slotContainer.addEventListener` |
| Spacebar trigger | Task 2 — `document.addEventListener('keydown')` |
| Spin physics: ramp-up, cruise, decelerate | Task 2 — `animate()` state machine |
| `isSpinning` guard | Task 2 — checked in `startSpin()` |
| Error: projects fail to load | Task 2 — `catch` block + `showError()` |
| Error: empty project list | Task 2 — `validateAndRender()` |
| Error: missing fields | Task 2 — conditional rendering in `showWinModal()` |
| Responsive design | Task 2 — CSS media queries |
| `prefers-reduced-motion` support | Task 2 — `prefersReducedMotion` check in `startSpin()` |
| Foundation-only styling | Task 2 — minimal, clean CSS |
| Standalone page + nav link | Task 3 — link from `site/index.html` |

**No gaps found. All spec requirements are covered.**

## Placeholder Scan

- [x] No "TBD", "TODO", "implement later", or "fill in details"
- [x] No vague "add error handling" — specific functions named (`showError`, `validateAndRender`)
- [x] No "similar to Task N" — each task is self-contained
- [x] No references to undefined types/functions

## Type Consistency Check

- [x] `projects` — array of project objects, used consistently across all tasks
- [x] `isSpinning` — boolean guard, checked in `startSpin()` and set in animation
- [x] `stripPosition` — number (px), updated after each spin and reset
- [x] `startSpin`, `showWinModal`, `closeModal`, `resetStrip` — function names consistent
- [x] `modalLink`, `modalTitle`, `modalDescription` — DOM refs consistent

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-04-slot-machine-wheel.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints

**Which approach?**
