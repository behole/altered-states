# Slot Machine Project Wheel — Design Spec

**Date:** 2026-05-04
**Status:** Approved

---

## 1. Overview

A single-page interactive slot machine that randomly selects a project from a configurable list. Users spin a vertical reel of project cards; the winner is revealed in a modal with a brief description and links to visit or spin again.

**Key decisions from brainstorming:**
- Vertical slot machine (not radial wheel)
- JS `requestAnimationFrame` animation loop (Approach B)
- Projects loaded from configurable JSON
- Win modal with description + "Visit Project" / "Spin Again" CTAs
- Three spin triggers: SPIN button, click/tap on slot, Spacebar

---

## 2. Architecture & Components

**Single HTML file** with embedded CSS and JS. No build step, no framework — vanilla HTML/CSS/JS matching the existing `site/index.html` style.

### Components

| Component | Description |
|-----------|-------------|
| `SlotContainer` | Outer viewport: fixed height, `overflow: hidden`, centers exactly one card |
| `Strip` | The vertically moving list of project cards; positioned via `translateY` |
| `SpinTrigger` | SPIN button + click/tap on slot area + Spacebar keyboard listener |
| `WinModal` | Overlay with project description + "Visit Project" / "Spin Again" buttons |
| `ProjectsData` | JS array loaded from configurable source (`projects.json` or inline fallback) |

---

## 3. Data Flow & Project Configuration

Projects are loaded at page load from `projects.json`. A fallback inline `<script type="application/json">` block is used if the fetch fails.

### Project Schema

```json
{
  "id": "project-1",
  "name": "Project Name",
  "description": "Brief description of the project.",
  "url": "https://example.com/project",
  "color": "#e74c3c"
}
```

**Note:** The `color` field is optional and intended for future custom styling (e.g., card borders or modal accent). The foundation implementation does not use it.

### Strip Rendering

The project list is duplicated 3× to ensure sufficient content for scrolling without visible gaps. The winner is determined mathematically from the final `translateY` position.

---

## 4. Spin Physics

A `requestAnimationFrame` loop drives the strip's `translateY`. The animation state machine has three phases:

1. **Ramp-up** (0–200ms): Velocity increases linearly from 0 to `maxSpeed`
2. **Cruise** (200ms–target): Maintain `maxSpeed` until within deceleration distance of target
3. **Deceleration** (ease-out cubic): Slow down smoothly, snapping the final position to center the winning card in the viewport

The target position is computed **before** the spin starts:
- Pick a random winner index
- Calculate the exact `translateY` that centers that card
- Work backwards to determine when to start decelerating

An `isSpinning` boolean prevents double-triggering. The spin is interruptible for future extensibility (e.g., "stop early" feature).

---

## 5. Win Modal

Triggered when the spin completes:

1. Semi-transparent backdrop fades in (`opacity 0 → 1`, 200ms)
2. Modal entrance:
   - **Mobile:** slides up from bottom
   - **Desktop:** scales in from center
3. Modal content:
   - Project name (large, bold)
   - Description (body text)
   - "Visit Project" button → opens `project.url` in new tab
   - "Spin Again" button → closes modal, resets strip to its initial neutral position (first project centered), re-enables spin

**Dismissal:** Clicking backdrop or pressing Escape closes the modal.

---

## 6. Triggers

| Trigger | Behavior |
|---------|----------|
| **SPIN button** | Primary CTA below the slot. Disabled while spinning (opacity + cursor). |
| **Click/tap on slot** | Works anywhere on the strip or viewport. Same as button. |
| **Spacebar** | Global listener. Ignored if user is typing in an input. Disabled while spinning. |

All triggers respect the `isSpinning` guard.

---

## 7. Error Handling

| Scenario | Behavior |
|----------|----------|
| Projects fail to load | Friendly error state in slot area: "Couldn't load projects" + retry button |
| Empty project list | Placeholder: "Add projects to spin!" |
| Missing `description` | Hide description section in modal |
| Missing `url` | Hide "Visit Project" button |
| Spin already in progress | All triggers noop. Button disabled, clicks/spacebar ignored. |

---

## 8. Styling (Foundation-Only)

The user will apply custom styling later. The foundation covers:

- **Slot viewport:** Fixed height (~160px), centered, subtle highlight/border for "winner zone"
- **Cards:** Clean rectangles, centered text, slight border. No heavy styling.
- **Button:** Basic styled button with disabled state while spinning.
- **Modal:** Centered overlay, clean typography, backdrop blur.
- **Responsive:** Mobile (full-width slot, bottom-sheet modal) and desktop (centered, max-width container).

No gradients, no extra animations beyond the spin, no heavy visual polish.

---

## 9. File Structure

```
site/
├── index.html              (existing site — add link to wheel)
└── wheel/
    ├── index.html          (the slot machine page)
    └── projects.json       (configurable project list)
```

The wheel is a standalone page linked from the main site. `projects.json` lives next to it for easy editing.

---

## 10. Open Questions / Future Enhancements

- Should the wheel page share the main site's nav/header/footer, or be a standalone experience?
- Sound effects on spin/win?
- Confetti or celebration animation on win?
- Weighted probabilities (some projects more likely than others)?
